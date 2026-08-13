// Post-deployment smoke gate for the CBSE CBA portal.
//
// Runs the cross-module smoke suite (M1-M5) against a freshly deployed
// environment and fails the build when a critical path is broken. Intended to
// be triggered by the deployment job — see docs/jenkins_setup.md for the two
// supported trigger styles and the credential setup this pipeline expects.
//
// Cross-platform by design: the suite is developed on Windows and typically
// runs on Linux agents, so every shell step goes through runShell() rather
// than hardcoding `sh`, which does not work on a Windows agent.

def runShell(String unixCommand, String windowsCommand) {
    if (isUnix()) {
        sh unixCommand
    } else {
        bat windowsCommand
    }
}

pipeline {
    agent any

    parameters {
        string(
            name: 'CBSE_BASE_URL',
            defaultValue: 'https://cbse-qa-new.akashic.dhira.io/',
            description: 'Environment just deployed. The smoke suite runs against this URL.'
        )
        string(
            name: 'WORKERS',
            defaultValue: '6',
            description: 'pytest-xdist workers. The suite has 10 account-isolated groups; 10 maximises parallelism but has shown connection contention against the QA environment, so 6 is the safer default.'
        )
        booleanParam(
            name: 'SKIP_WRITE_CHECKS',
            defaultValue: false,
            description: 'Skip the Excel ingestion check, which mints a real item set into the RWG queue. Leave off for a true gate; turn on for shared or pre-release environments.'
        )
    }

    options {
        timeout(time: 40, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '30'))
        disableConcurrentBuilds()
    }

    environment {
        // The suite drives one portal session per account, so two concurrent
        // builds would sign each other out. disableConcurrentBuilds() above is
        // what actually enforces that; this block only carries configuration.
        CBSE_BASE_URL = "${params.CBSE_BASE_URL}"
        CBSE_HEADLESS = '1'
        PYTEST_REPORTS_DIR = "${WORKSPACE}/reports_smoke_ci"
        // A Jenkins agent has no ~/Downloads, so point the Excel check at the
        // template vendored in the repo.
        CBSE_UPLOAD_ITEM_FILE = "${WORKSPACE}/data/upload_templates/sme_sheet.xlsx"
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set up Python') {
            steps {
                script {
                    runShell(
                        '''
                            set -eu
                            python3 -m venv .venv
                            . .venv/bin/activate
                            pip install -q -r requirements.txt
                            pip install -q pytest-xdist
                        ''',
                        '''
                            python -m venv .venv || exit /b 1
                            call .venv\\Scripts\\activate.bat || exit /b 1
                            pip install -q -r requirements.txt || exit /b 1
                            pip install -q pytest-xdist || exit /b 1
                        '''
                    )
                }
            }
        }

        stage('Load credentials') {
            steps {
                // The suite reads every account from the environment, and .env
                // is gitignored so those passwords never reach the repo. The
                // Secret file credential is the only place they live for CI.
                withCredentials([file(credentialsId: 'cbse-smoke-env', variable: 'CBSE_ENV_FILE')]) {
                    script {
                        runShell(
                            'cp "$CBSE_ENV_FILE" .env',
                            'copy /Y "%CBSE_ENV_FILE%" .env'
                        )
                    }
                }
            }
        }

        stage('Preflight') {
            steps {
                // A stalled or half-booted environment fails every check for
                // the same reason and buries the real signal. One cheap login
                // against the deployed build tells us whether the app actually
                // renders before spending the full suite's runtime on it.
                script {
                    runShell(
                        '''
                            set -eu
                            . .venv/bin/activate
                            python -m pytest tests/M3_Item_Testing/test_smoke_m3_item_testing.py \
                                -p no:cacheprovider --no-header -q
                        ''',
                        '''
                            call .venv\\Scripts\\activate.bat || exit /b 1
                            python -m pytest tests/M3_Item_Testing/test_smoke_m3_item_testing.py -p no:cacheprovider --no-header -q || exit /b 1
                        '''
                    )
                }
            }
        }

        stage('Smoke') {
            steps {
                script {
                    // -k excludes the only check that writes; see the parameter
                    // description.
                    def deselect = params.SKIP_WRITE_CHECKS
                        ? '-k "not excel_upload_creates_item_set"'
                        : ''
                    runShell(
                        """
                            set -eu
                            . .venv/bin/activate
                            python -m pytest -m smoke ${deselect} \
                                -n ${params.WORKERS} --dist loadgroup \
                                --junitxml=reports_smoke_ci/junit.xml \
                                --html=reports_smoke_ci/report.html --self-contained-html \
                                -p no:cacheprovider
                        """,
                        """
                            call .venv\\\\Scripts\\\\activate.bat || exit /b 1
                            python -m pytest -m smoke ${deselect} -n ${params.WORKERS} --dist loadgroup --junitxml=reports_smoke_ci/junit.xml --html=reports_smoke_ci/report.html --self-contained-html -p no:cacheprovider
                        """
                    )
                }
            }
        }
    }

    post {
        always {
            // allowEmptyResults keeps an environment-level failure (suite never
            // started) reporting as a build failure rather than masking it as a
            // Jenkins config error about missing results.
            junit testResults: 'reports_smoke_ci/junit.xml', allowEmptyResults: true
            archiveArtifacts(
                artifacts: 'reports_smoke_ci/**/*, screenshots/**/*',
                allowEmptyArchive: true,
                fingerprint: false
            )
            publishHTML(target: [
                reportDir: 'reports_smoke_ci',
                reportFiles: 'report.html,extent_report.html',
                reportName: 'CBSE Smoke Report',
                keepAll: true,
                alwaysLinkToLastBuild: true,
                allowMissing: true
            ])
        }
        unstable {
            echo 'Smoke suite reported test failures — see the CBSE Smoke Report for the failing module.'
        }
        cleanup {
            // Remove the decrypted .env first — it holds real account
            // passwords and must not sit in the workspace between builds.
            // Screenshots run to hundreds of MB across builds; the archive
            // above already captured this build's copy.
            script {
                runShell(
                    'rm -f .env; rm -rf screenshots/* || true',
                    'if exist .env del /f /q .env & if exist screenshots rmdir /s /q screenshots & exit /b 0'
                )
            }
        }
    }
}
