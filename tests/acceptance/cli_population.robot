*** Settings ***
Resource    resources/keywords.resource
Resource    resources/variables.resource

*** Variables ***

*** Test Cases ***
Cli Should Populate App With Keywords From Provided Paths Only
    [Documentation]    Cli Should Populate App With Keywords From Provided Paths Only
    Run Cli Package Without Installed Keywords
    Output Should Contain
    ...    LibWithInit library with 4 keywords loaded.
    ...    Test Libdoc File library with 1 keywords loaded.
    ...    LibWithEmptyInit1 library with 2 keywords loaded.
    ...    test_resource library with 2 keywords loaded.
    ...    SingleClassLib library with 3 keywords loaded.
    ...    LibWithEmptyInit2 library with 2 keywords loaded.
    ...    test_robot library with 4 keywords loaded.
    ...    Successfully loaded 7 collections with 18 keywords.
    Api Should Have With 7 Collections And 18 Keywords

Cli Should Populate App With Installed Keywords
    [Documentation]    Cli Should Populate App With Installed Keywords
    Run Cli Package
    Output Should Contain
    ...    Collections library with 43 keywords loaded.
    ...    XML library with 37 keywords loaded.
    ...    Easter library with 1 keywords loaded.
    ...    Process library with 15 keywords loaded.
    ...    String library with 31 keywords loaded.
    ...    DateTime library with 8 keywords loaded.
    ...    OperatingSystem library with 56 keywords loaded.
    ...    Screenshot library with 3 keywords loaded.
    ...    BuiltIn library with 104 keywords loaded.
    ...    Telnet library with 20 keywords loaded.
    ...    Successfully loaded 10 collections with 318 keywords.
    Api Should Have With 10 Collections And 100 Keywords

Cli Should Preserve All Keywords When Paths And No Db Flush Set
    [Documentation]    Cli Should Preserve All Keywords When Paths And No Db Flush Set
    ...                This test is dependant on one above:
    ...                'Cli Should Populate App With Installed Keywords'
    Run Cli Package With Options    --mode=append --no-installed-keywords
    Output Should Contain
    ...    Successfully loaded 0 collections with 0 keywords.
    Api Should Have With 10 Collections And 100 Keywords

Cli Should Delete All Keywords When Paths And No Installed Keywords Set
    [Documentation]    Cli Should Delete All Keywords When Paths And No Installed Keywords Set
    Run Cli Package With Options    --no-installed-keywords
    Output Should Contain
    ...    Successfully loaded 0 collections with 0 keywords.
    Api Should Have With 0 Collections And 0 Keywords

Cli Should Return Unauthorised When Wrong User Given
    [Documentation]    Cli Should Return Unauthorised When Wrong User Given
    Run Cli Package With Options    -u wrong_user
    Output Should Contain    Unauthorized to perform this action

Cli Should Return Unauthorised When Wrong Password Given
    [Documentation]    Cli Should Return Unauthorised When Wrong Password Given
    Run Cli Package With Options    -p wrong_pass
    Output Should Contain    Unauthorized to perform this action

Cli Should Return Connection Error When Wrong Url Given
    [Documentation]    Cli Should Return Connection Error When Wrong Url Given
    Run Cli Package With Options    -a 123.456.789.123:666
    Should Contain    ${output}    No connection adapters were found

Cli Should Update Existing Collections, Delete Obsolete And Add New
    [Documentation]     Cli Should Update Existing Collections, 
    ...    Delete Obsolete And Add New.
    [Tags]    rfhub2-64
    [Setup]    Run Keywords
    ...    Run Cli Package Without Installed Keywords
    ...    Backup And Switch Initial With Updated Fixtures
    Run Cli Package With Options
    ...    --mode=update --no-installed-keywords ${INITIAL_FIXTURES}
    Output Should Contain
    ...    SingleClassLib library with 4 keywords loaded.
    ...    test_resource library with 2 keywords loaded.
    ...    Test Libdoc File library with 1 keywords loaded.
    ...    Test Libdoc File Copy library with 1 keywords loaded.

Cli Update Mode Should Leave Application With New Set Of Collections
    [Documentation]     Cli Update Mode Should Leave Application 
    ...    With New Set Of Collections. This test bases on 
    ...    'Cli Should Update Existing Collections, Delete Obsolete And Add New' 
    ...    to speed up execution
    [Tags]    rfhub2-64
    Api Should Have With 7 Collections And 16 Keywords
    
Running Cli Update Mode Second Time Should Leave Collections Untouched
    [Documentation]    Running Cli Update Mode Second Time 
    ...    Should Leave Collections Untouched. This test bases on 
    ...    'Cli Should Update Existing Collections, Delete Obsolete And Add New' 
    ...    to speed up execution
    Run Cli Package With Options
    ...    --mode=update --no-installed-keywords ${INITIAL_FIXTURES}
    Output Should Contain    Successfully loaded 0 collections with 0 keywords.
    [Teardown]    Run Keywords    Restore Initial Fixtures    AND
    ...    Run Cli Package With Options
    ...    --mode=insert --no-installed-keywords

*** Keywords ***
Api Should Have With ${n} Collections And ${m} Keywords
    collections Endpoint Should Have ${n} Items
    keywords Endpoint Should Have ${m} Items
