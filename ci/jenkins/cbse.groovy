// Shared steps for the CBSE CBA Jenkins pipelines.
//
// Loaded once per build, after `checkout scm`:
//
//     def cbse
//     ...
//     steps { script { cbse = load 'ci/jenkins/cbse.groovy' } }
//
// Everything here is cross-platform: the suite is developed on Windows and
// typically runs on Linux agents, so no step hardcodes `sh`.

/** Run the unix or the windows form of a command, depending on the agent. */
def runShell(String unixCommand, String windowsCommand) {
    if (isUnix()) {
        sh unixCommand
    } else {
        bat windowsCommand
    }
}

/**
 * Create .venv if it is missing, then install requirements.
 *
 * The venv is deliberately reused rather than recreated: recreating fails
 * outright when a previous build was aborted and its python.exe still holds
 * the file, and it costs ~40s even when it works. pip still runs every build,
 * so a changed requirements.txt is always picked up.
 */
def setUpPython() {
    runShell(
        '''
            set -eu
            [ -x .venv/bin/python ] || python3 -m venv .venv
            . .venv/bin/activate
            pip install -q -r requirements.txt
            pip install -q pytest-xdist
        ''',
        '''
            if not exist .venv\\Scripts\\python.exe python -m venv .venv || exit /b 1
            call .venv\\Scripts\\activate.bat || exit /b 1
            pip install -q -r requirements.txt || exit /b 1
            pip install -q pytest-xdist || exit /b 1
        '''
    )
}

/**
 * Drop the Secret file credential into the workspace as .env.
 *
 * The suite reads every account from the environment, and .env is gitignored
 * so those passwords never reach the repo. Always pair this with
 * removeEnvFile() in post/cleanup — a decrypted .env must not sit in the
 * workspace between builds.
 */
def installEnvFile(String credentialsId) {
    withCredentials([file(credentialsId: credentialsId, variable: 'CBSE_ENV_FILE')]) {
        runShell(
            'cp "$CBSE_ENV_FILE" .env',
            'copy /Y "%CBSE_ENV_FILE%" .env'
        )
    }
}

def removeEnvFile() {
    runShell(
        'rm -f .env || true',
        'if exist .env del /f /q .env & exit /b 0'
    )
}

/**
 * Run pytest and hand back its exit code instead of failing the step.
 *
 * The caller decides what each code means — see classifyPytestResult() — so a
 * test failure can land as UNSTABLE while a broken agent lands as FAILURE.
 * Activation problems exit 9 so they can never be mistaken for pytest's 1.
 */
int runPytest(String pytestArgs) {
    if (isUnix()) {
        return sh(
            returnStatus: true,
            script: """
                . .venv/bin/activate || exit 9
                python -m pytest ${pytestArgs}
            """
        )
    }
    return bat(
        returnStatus: true,
        script: """
            call .venv\\Scripts\\activate.bat || exit /b 9
            python -m pytest ${pytestArgs}
            exit /b %ERRORLEVEL%
        """
    )
}

/**
 * Turn a pytest exit code into a build result.
 *
 * 0  all selected tests passed (xfail and skip included)
 * 1  tests failed          -> UNSTABLE, so every other lane still finishes and
 *                             the reports below still publish
 * 2  interrupted (timeout, aborted build)
 * 3  internal error        -> a broken conftest or plugin, not a product bug
 * 4  usage error           -> a bad marker expression or path in this pipeline
 * 5  nothing collected     -> a lane silently testing nothing, which for a
 *                             "complete" run is a pipeline bug, not a pass
 */
def classifyPytestResult(String laneName, int code) {
    if (code == 0) {
        return
    }
    if (code == 1) {
        unstable("${laneName}: tests failed — open the ${laneName} report.")
        return
    }
    if (code == 5) {
        error("${laneName}: pytest collected no tests. Check the paths and marker expression.")
    }
    error("${laneName}: pytest exited ${code} (not a test failure — the run itself broke).")
}

/** Run a lane and classify it in one call. */
def runLane(String laneName, String pytestArgs) {
    classifyPytestResult(laneName, runPytest(pytestArgs))
}

/**
 * Standard pytest flags for any CI lane.
 *
 * -p no:cacheprovider matters here beyond tidiness: the full pipeline runs
 * several pytest processes concurrently in one workspace, and they would
 * otherwise contend for .pytest_cache.
 */
String reportingArgs(String reportsDir) {
    // Quoted: a Jenkins workspace path can contain spaces, and these are
    // absolute paths built from ${WORKSPACE}.
    return "--color=yes -p no:cacheprovider " +
        "--junitxml=\"${reportsDir}/junit.xml\" " +
        "--html=\"${reportsDir}/report.html\" --self-contained-html"
}

/**
 * Build the -m expression.
 *
 * Always pass a complete expression. pytest.ini already sets
 * `-m "not nightly"` in addopts and `-m` is single-valued, so a bare
 * `-m smoke` on the command line *replaces* that and quietly drags the
 * nightly AI-verdict tests back into the run.
 */
String markerArgs(List<String> clauses, boolean includeNightly) {
    List<String> parts = clauses.findAll { it?.trim() }
    if (!includeNightly) {
        parts += 'not nightly'
    } else if (parts.isEmpty()) {
        // pytest rejects an empty -m, and omitting -m would let addopts'
        // `not nightly` win. This tautology selects everything.
        parts += 'nightly or not nightly'
    }
    return '-m "' + parts.join(' and ') + '"'
}

/**
 * xdist flags.
 *
 * --dist loadgroup is not optional: the portal allows one active session per
 * account and the suite encodes that as xdist_group markers (per-account
 * groups, plus one global `serial` group). Any other scheduler spreads tests
 * that share an account across workers and they sign each other out.
 */
String xdistArgs(String workers) {
    if (!workers || workers == '0' || workers == '1') {
        return ''
    }
    return "-n ${workers} --dist loadgroup"
}

/** Retry flags, or nothing at all when reruns are off. */
String rerunArgs(String reruns) {
    if (!reruns || reruns == '0') {
        return ''
    }
    return "--reruns ${reruns} --reruns-delay 5"
}

/** Publish one lane's reports. Safe to call for a lane that never ran. */
def publishLane(String reportsDirName, String reportName) {
    publishHTML(target: [
        reportDir: reportsDirName,
        reportFiles: 'extent_report.html,report.html',
        repo