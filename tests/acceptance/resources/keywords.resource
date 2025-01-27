*** Settings ***
Library    SeleniumLibrary
Library    OperatingSystem
Library    Process
Library    RequestsLibrary
Library    Collections

*** Keywords ***
Start Rfhub2
    [Arguments]    @{options}
    [Documentation]
    ...    Starts rfhub2 on the port given in the variable \${PORT}
    ...    As a side effect this creates a suite variable named \${rfhub process},
    ...    which is used by the 'Stop rfhub2' keyword.
    ${rfhub2_process}    Start Process    ${ACTIVATE_VENV} ${DB_URI} rfhub2    shell=True
    Set Suite Variable    ${rfhub2_process}
    Wait Until Keyword Succeeds    20 seconds    0.5 second
    ...    Verify URL Is Reachable    /api/v1/health

Stop Rfhub2
    [Documentation]
    ...    Stops the rfhub2 process created by "Start Rfhub2"
    Terminate Process    ${rfhub2_process}
    ${result}    Get Process Result
    Run Keyword If    len('''${result.stderr}''') > 0
    ...    Log    rfhub2 stderr: ${result.stderr}    DEBUG
    
Open Browser With App On Mainpage
    Open Browser    url=localhost:8000    browser=gc
    Maximize Browser Window

Navigate To Main Page
    Go To    localhost:8000

Collections Count On Main Page Should Be ${n}
    Reload Page
    Run Keyword If    '${n}'!='0'    Wait Until Element Is Visible    ${main_page_table}
    Element Text Should Be    ${main_page_collection_number}    Collections (${n})

Run Cli Package With Options
    [Arguments]    ${options}
    [Documentation]
    ...    Attempt to run the rfhub2-cli package with the given options
    ...    The stdout of the process will be in a test suite
    ...    variable named \${output}
    ${output}    Run    ${ACTIVATE_VENV} rfhub2-cli ${options}
    Set Suite Variable    ${output}

Run Cli Package
    [Documentation]
    ...    Attempt to run the rfhub2-cli package with the default options
    ...    The stdout of the process will be in a test suite
    ...    variable named \${output}
    ${output}    Run    ${ACTIVATE_VENV} rfhub2-cli
    Set Suite Variable    ${output}

Output Should Contain
    [Arguments]    @{patterns}
    [Documentation]
    ...    Fail if the output from the previous command doesn't contain the given string
    ...    This keyword assumes the output of the command is in
    ...    a test suite variable named \${output}
    ...    Note: the help will be automatically wrapped, so
    ...    you can only search for relatively short strings.
    FOR    ${pattern}    IN    @{patterns}
        Run keyword if    '''${pattern}''' not in '''${output}'''
        ...    Fail    Output did not contain '${pattern}'
    END

Verify URL Is Reachable
    # This could be useful in more places than just API tests.
    # Maybe it should be moved to a different file...
    [Arguments]    ${URL}    ${PORT}=8000
    [Documentation]    Fail if the given URL doesn't return a status code of 200.
    Create Session    tmp    http://localhost:${PORT}
    ${response}    Get Request    tmp    ${url}
    Should Be Equal As Integers    ${response.status_code}    200

${endpoint} Endpoint Should Have ${n} Items
    Create Session    tmp    http://localhost:8000/api/v1
    ${response}    Get Request    tmp    ${endpoint}/
    Should Be Equal As Integers    ${response.status_code}    200
    ${response_content}    Set Variable    ${response.json()}
    Length Should Be    ${response_content}    ${n}

Run Cli Package Without Installed Keywords
    Run Cli Package With Options    --no-installed-keywords ${INITIAL_FIXTURES}

Backup And Switch Initial With Updated Fixtures
    Move Directory      ${INITIAL_FIXTURES}    ${BACKUP_FIXTURES}
    Copy Directory      ${UPDATED_FIXTURES}    ${INITIAL_FIXTURES}

Restore Initial Fixtures
    Remove Directory    ${INITIAL_FIXTURES}    recursive=True
    Copy Directory      ${BACKUP_FIXTURES}     ${INITIAL_FIXTURES}
    Remove Directory    ${BACKUP_FIXTURES}     recursive=True