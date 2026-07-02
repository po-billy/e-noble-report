StatReport
Methods
list
GET /stat-reports
Retrieves all of the registered Report Jobs

get
GET /stat-reports/reportJobId
Retrieves a registered Report Job

create
POST /stat-reports
Registers a Report Job

delete
DELETE /stat-reports
Delete Report Jobs

delete
DELETE /stat-reports/reportJobId
Deletes a Report Job

StatReport: list
Retrieves all of the registered Report Jobs

Request
HTTP request
GET /stat-reports
Parameters
Parameter name	Data type	Description

Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

아래 항목이 배열으로 존재합니다.
Property name	Data type	Description
downloadUrl	string	
Download URL

The download address of a file

reportJobId	long	
ID of a Report Job

reportTp	string	
Type of ad performance Report


reportTp의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the reportTp.Valid items are:

AD
AD_DETAIL
AD_CONVERSION
AD_CONVERSION_DETAIL
ADEXTENSION
ADEXTENSION_CONVERSION
EXPKEYWORD
SHOPPINGKEYWORD_DETAIL
SHOPPINGKEYWORD_CONVERSION_DETAIL
SHOPPINGBRANDPRODUCT
SHOPPINGBRANDPRODUCT_CONVERSION
CRITERION
CRITERION_CONVERSION
statDt	string	
Effective date

yyyy-MM-ddTHH:mm:ssZ (ISO8601)

status	string	
Job status, REGIST, RUNNING, BUILT, NONE, ERROR, WAITING, AGGREGATING


status의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the status.Valid items are:

REGIST
RUNNING
BUILT
NONE
ERROR
WAITING
AGGREGATING
updateTm	string	
최근 수정 시각

Recently modified time

yyyy-MM-ddTHH:mm:ssZ (ISO8601)


StatReport: get
Retrieves a registered Report Job

Request
HTTP request
GET /stat-reports/{reportJobId}
Parameters
Parameter name	Data type	Description
Path parameters
reportJobId	ref	
ID of a Report Job


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
downloadUrl	string	
Download URL

The download address of a file

reportJobId	long	
ID of a Report Job

reportTp	string	
Type of ad performance Report


reportTp의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the reportTp.Valid items are:

AD
AD_DETAIL
AD_CONVERSION
AD_CONVERSION_DETAIL
ADEXTENSION
ADEXTENSION_CONVERSION
EXPKEYWORD
SHOPPINGKEYWORD_DETAIL
SHOPPINGKEYWORD_CONVERSION_DETAIL
SHOPPINGBRANDPRODUCT
SHOPPINGBRANDPRODUCT_CONVERSION
CRITERION
CRITERION_CONVERSION
statDt	string	
Effective date

yyyy-MM-ddTHH:mm:ssZ (ISO8601)

status	string	
Job status, REGIST, RUNNING, BUILT, NONE, ERROR, WAITING, AGGREGATING


status의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the status.Valid items are:

REGIST
RUNNING
BUILT
NONE
ERROR
WAITING
AGGREGATING
updateTm	string	
최근 수정 시각

Recently modified time

yyyy-MM-ddTHH:mm:ssZ (ISO8601)

StatReport: create
Registers a Report Job

Request
HTTP request
POST /stat-reports
Parameters
Parameter name	Data type	Description
Request body
reportTp	string	
Type of ad performance Report


reportTp의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the reportTp.Valid items are:

AD
AD_DETAIL
AD_CONVERSION
AD_CONVERSION_DETAIL
ADEXTENSION
ADEXTENSION_CONVERSION
EXPKEYWORD
SHOPPINGKEYWORD_DETAIL
SHOPPINGKEYWORD_CONVERSION_DETAIL
SHOPPINGBRANDPRODUCT
SHOPPINGBRANDPRODUCT_CONVERSION
CRITERION
CRITERION_CONVERSION
statDt	string	
Effective date

YYYYMMDD (KST), yyyy-MM-ddTHH:mm:ssZ (ISO8601) are allowed


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
downloadUrl	string	
Download URL

The download address of a file

reportJobId	long	
ID of a Report Job

reportTp	string	
Type of ad performance Report


reportTp의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the reportTp.Valid items are:

AD
AD_DETAIL
AD_CONVERSION
AD_CONVERSION_DETAIL
ADEXTENSION
ADEXTENSION_CONVERSION
EXPKEYWORD
SHOPPINGKEYWORD_DETAIL
SHOPPINGKEYWORD_CONVERSION_DETAIL
SHOPPINGBRANDPRODUCT
SHOPPINGBRANDPRODUCT_CONVERSION
CRITERION
CRITERION_CONVERSION
statDt	string	
Effective date

yyyy-MM-ddTHH:mm:ssZ (ISO8601)

status	string	
Job status, REGIST, RUNNING, BUILT, NONE, ERROR, WAITING, AGGREGATING


status의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the status.Valid items are:

REGIST
RUNNING
BUILT
NONE
ERROR
WAITING
AGGREGATING
updateTm	string	
최근 수정 시각

Recently modified time

yyyy-MM-ddTHH:mm:ssZ (ISO8601)

StatReport: delete
Delete Report Jobs

Request
HTTP request
DELETE /stat-reports
Parameters
Parameter name	Data type	Description

Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description


StatReport: delete
Deletes a Report Job

Request
HTTP request
DELETE /stat-reports/{reportJobId}
Parameters
Parameter name	Data type	Description
Path parameters
reportJobId	ref	
ID of a Report Job


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
