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

// Run the unix or the windows form of a command, depending on the agent.
def runShell(String unixCommand, String windowsCommand) {
    if (isUnix()) {
        sh unixCommand
    } else {
        bat windowsCommand
    }
}

// Create .venv if it is missing, then install requirements.
//
// The venv is deliberately reused rather than recreated: recreating fails
// outright when a previous build was aborted and its python.exe still holds the
// file, and it costs ~40s even when it works. pip still runs every build, so a
// changed requirements.txt is always picked up.
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

// Drop the Secret file credential into the workspace as .env.
//
// The suite reads every account from the environment, and .env is gitignored so
// those passwords never reach the repo. Always pair this with removeEnvFile()
// in post/cleanup - a decrypted .env must not sit in the workspace between
// builds.
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

// Run pytest and hand back its exit code instead of failing the step.
//
// The caller decides what each code means - see classifyPytestResult() - so a
// test failure can land as UNSTABLE while a broken agent lands as FAILURE.
// Activation problems exit 9 so they can never be mistaken for pytest exit 1.
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

// Turn a pytest exit code into a build result.
//
// 0  all selected tests passed (xfail and skip included)
// 1  tests failed          -> UNSTABLE, so every other lane still finishes and
//                             the reports still publish
// 2  interrupted (timeout, aborted build)
// 3  internal error        -> a broken conftest or plugin, not a product bug
// 4  usage error           -> a bad marker expression or path in this pipeline
// 5  nothing collected     -> a lane silently testing nothing, which for a
//                             "complete" run is a pipeline bug, not a pass
def classifyPytestResult(String laneName, int code) {
    if (code == 0) {
        return
    }
    if (code == 1) {
        unstable("${laneName}: tests failed - open the ${laneName} report.")
        return
    }
    if (code == 5) {
        error("${laneName}: pytest collected no tests. Check the paths and marker expression.")
    }
    error("${laneName}: pytest exited ${code} (not a test failure - the run itself broke).")
}

// Run a lane and classify it in one call.
def runLane(String laneName, String pytestArgs) {
    classifyPytestResult(laneName, runPytest(pytestArgs))
}

// Standard pytest flags for any CI lane.
//
// -p no:cacheprovider matters here beyond tidiness: the full pipeline runs
// several pytest processes concurrently in one workspace, and they would
// otherwise contend for .pytest_cache. The report paths are quoted because a
// Jenkins workspace path can contain spaces.
String reportingArgs(String reportsDir) {
    return "--color=yes -p no:cacheprovider " +
        "--junitxml=\"${reportsDir}/junit.xml\" " +
        "--html=\"${reportsDir}/report.html\" --self-contained-html"
}

// Build the -m expression.
//
// Always pass a complete expression. pytest.ini already sets `-m "not nightly"`
// in addopts and `-m` is single-valued, so a bare `-m smoke` on the command
// line *replaces* that and quietly drags the nightly AI-verdict tests back into
// the run.
String markerArgs(List<String> clauses, boolean includeNightly, boolean includePerformance = false) {
    List<String> parts = clauses.findAll { it?.trim() }
    if (!includeNightly) {
        parts += 'not nightly'
    }
    // TC-IBMM-08-P01 measures QAR wall-clock against a 120s budget this
    // environment does not meet, so it is a standing red on any gate. Worse,
    // under -n its number is measured while other workers hammer the same QAR
    // backend, so the contention lands inside the measurement. Excluded here
    // and run on its own instead - the assertion stays hard, it just does not
    // block a deploy. Run it with: pytest -m performance
    if (!includePerformance) {
        parts += 'not performance'
    }
    // pytest.ini's addopts also excludes `deferred` - tests parked on something
    // the environment cannot supply (a mailbox, a feature not in this build).
    // Replacing -m drops that clause too, and they then fail on every run.
    // (It also keeps the expression non-empty, which pytest requires.)
    parts += 'not deferred'
    return '-m "' + parts.join(' and ') + '"'
}

// xdist flags.
//
// --dist loadgroup is not optional: the portal allows one active session per
// account and the suite encodes that as xdist_group markers (per-account
// groups, plus one global `serial` group). Any other scheduler spreads tests
// that share an account across workers and they sign each other out.
String xdistArgs(String workers) {
    if (!workers || workers == '0' || workers == '1') {
        return ''
    }
    return "-n ${workers} --dist loadgroup"
}

// Retry flags, or nothing at all when reruns are off.
String rerunArgs(String reruns) {
    if (!reruns || reruns == '0') {
        return ''
    }
    return "--reruns ${reruns} --reruns-delay 5"
}

// Publish one lane's reports. Safe to call for a lane that never ran.
def publishLane(String reportsDirName, String reportName) {
    publishHTML(target: [
        reportDir: reportsDirName,
        reportFiles: 'extent_report.html,report.html',
        reportName: reportName,
        keepAll: true,
        alwaysLinkToLastBuild: true,
        allowMissing: true
    ])
}

// Merge every lane's junit.xml into one module-level report.
//
// Writes <reportsDir>/daily_summary.html and returns the one-line status used
// as the mail subject, or null when the summary could not be built (typically
// because the build failed before .venv existed). Never fails the build: the
// report is a courtesy on top of the result, not part of it.
String buildSummary(String reportsDir, String title) {
    String duration = currentBuild.durationString.replace(' and counting', '')
    String args = "--reports-dir \"${reportsDir}\" --title \"${title}\" " +
        "--env-url \"${env.CBSE_BASE_URL}\" --build-url \"${env.BUILD_URL ?: ''}\" " +
        "--duration \"${duration}\""
    int code = isUnix()
        ? sh(returnStatus: true, script: ". .venv/bin/activate && python tools/build_daily_summary.py ${args}")
        : bat(returnStatus: true, script: "call .venv\\Scripts\\activate.bat && python tools\\build_daily_summary.py ${args}")
    if (code != 0) {
        echo "Summary report was not built (exit ${code}); the lane reports are still published."
        return null
    }
    return readFile("${reportsDir}/daily_summary.txt").trim()
}

// Merge every lane's results into one Extent report and workbook covering all
// modules, in <reportsDir>/all_modules. Run it before the workspace's
// screenshots/ are cleaned: the report embeds them from there. Never fails the
// build; the lane reports are still published without it.
def buildCombinedReport(String reportsDir, String title) {
    String args = "--reports-dir \"${reportsDir}\" --title \"${title}\""
    int code = isUnix()
        ? sh(returnStatus: true, script: ". .venv/bin/activate && python tools/build_combined_report.py ${args}")
        : bat(returnStatus: true, script: "call .venv\\Scripts\\activate.bat && python tools\\build_combined_report.py ${args}")
    if (code != 0) {
        echo "All-modules report was not built (exit ${code}); the lane reports are still published."
    }
}

// Mail the summary to the team. Needs the Email Extension plugin.
//
// An empty recipient list falls back to $DEFAULT_RECIPIENTS, the team list set
// once under Manage Jenkins > System > Extended E-mail Notification, so the
// list is not hardcoded here. The body uses the FILE token rather than
// readFile() so that `$` in a failure message is not expanded as a token.
def emailSummary(String reportsDir, String subject, String recipients) {
    String to = recipients?.trim() ?: '$DEFAULT_RECIPIENTS'
    if (subject == null) {
        emailext(
            to: to,
            subject: "${env.JOB_BASE_NAME} #${env.BUILD_NUMBER} - ${currentBuild.currentResult}: no test results",
            mimeType: 'text/html',
            body: "<p>The run stopped before any tests produced results.</p>" +
                  "<p><a href='${env.BUILD_URL}console'>Open the console log</a></p>"
        )
        return
    }
    // The all-modules workbook rides along: every test's result and reason in
    // one file. The HTML report embeds its screenshots and is far too large to
    // mail, so the body links to it instead. A missing workbook just goes
    // unattached.
    emailext(
        to: to,
        subject: subject,
        mimeType: 'text/html',
        body: "\${FILE,path=\"${reportsDir}/daily_summary.html\"}",
        attachmentsPattern: "${reportsDir}/all_modules/excel_report.xlsx"
    )
}

return this
