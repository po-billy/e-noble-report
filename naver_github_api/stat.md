Stat
Methods
get (by id)
GET /stats?id,fields,timeRange,datePreset,timeIncrement,breakdown
Receive the Summary Report per single entity

get (by ids)
GET /stats?ids,fields,timeRange,datePreset,timeIncrement,breakdown
Receive the Summary Report per multiple entities

get (by statType)
GET /stats?id,statType
Receive the Customized Report per stat type and single entity



Stat: get (by id)
Receive the Summary Report per single entity

Request
HTTP request
GET /stats{?id,fields,timeRange,datePreset,timeIncrement,breakdown}
Parameters
Parameter name	Data type	Description
Query parameters
id	string	
Entity Id (campaign id, Ad group id, Ad keyword id, Ad id, Criterion id)

fields	string	
Fields to be retrieved (JSON format string).

For example, ["impCnt","clkCnt","salesAmt","crto"]


fields의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the fields.Valid items are:

impCnt
clkCnt
salesAmt
ctr
cpc
avgRnk
ccnt
recentAvgRnk
recentAvgCpc
pcNxAvgRnk
mblNxAvgRnk
crto
convAmt
ror
cpConv
viewCnt
purchaseCcnt
purchaseConvAmt
purchaseRor
timeRange	string	
Hours of stats based on KST (JSON format string). This parameter is ignored if datePreset is provided

For example, {"since":"YYYY-MM-DD","until":"YYYY-MM-DD"}

datePreset	string	Optional
Predefined period of stats. This parameter is ignored if timeRange is provided


datePreset의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the datePreset.Valid items are:

today
yesterday
last7days
last30days
lastweek
lastmonth
lastquarter
timeIncrement	string	Optional
Selection of daily aggregated stats(1) or summary stats(allDays). Default value is 1


timeIncrement의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the timeIncrement.Valid items are:

1
allDays
breakdown	string	Optional
Stat classification type. Dose not support more than one breakdown. Default value is empty


breakdown의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the breakdown.Valid items are:

pcMblTp
dayw
hh24
regnNo

Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
dailyStatResponse	DailyStatResponse	
Return daily stats data structure if timeInrcement is 1

summaryStatResponse	SummaryStatResponse	
Return summation stats data structure if timeInrcement is allDays


Stat: get (by ids)
Receive the Summary Report per multiple entities

Request
HTTP request
GET /stats{?ids,fields,timeRange,datePreset,timeIncrement,breakdown}
Parameters
Parameter name	Data type	Description
Query parameters
ids	string	
Entity Id List (campaign id, Ad group id, Ad keyword id, Ad id, Criterion id)

fields	string	
Fields to be retrieved (JSON format string).

For example, ["impCnt","clkCnt","salesAmt","crto"]


fields의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the fields.Valid items are:

impCnt
clkCnt
salesAmt
ctr
cpc
avgRnk
ccnt
recentAvgRnk
recentAvgCpc
pcNxAvgRnk
mblNxAvgRnk
crto
convAmt
ror
cpConv
viewCnt
purchaseCcnt
purchaseConvAmt
purchaseRor
timeRange	string	
Hours of stats based on KST (JSON format string). This parameter is ignored if datePreset is provided

For example, {"since":"YYYY-MM-DD","until":"YYYY-MM-DD"}

datePreset	string	Optional
Predefined period of stats. This parameter is ignored if timeRange is provided


datePreset의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the datePreset.Valid items are:

today
yesterday
last7days
last30days
lastweek
lastmonth
lastquarter
timeIncrement	string	Optional
Selection of daily aggregated stats(1) or summary stats(allDays). Default value is allDays


timeIncrement의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the timeIncrement.Valid items are:

allDays
breakdown	string	Optional
Stat classification type. Dose not support more than one breakdown. Default value is empty


breakdown의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the breakdown.Valid items are:

pcMblTp
dayw
hh24
regnNo

Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
dailyStatResponse	DailyStatResponse	
Return daily stats data structure if timeInrcement is 1

summaryStatResponse	SummaryStatResponse	
Return summation stats data structure if timeInrcement is allDays


Stat: get (by statType)
Receive the Customized Report per stat type and single entity

Request
HTTP request
GET /stats{?id,statType}
Parameters
Parameter name	Data type	Description
Query parameters
id	string	
Entity Id

statType	string	
Predefined stat type. For example, NPLA_SCH_KEYWORD


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

아래 항목이 배열으로 존재합니다.
Property name	Data type	Description
impCnt	integer	
clkCnt	integer	
drtCrto	number	
salesAmt	integer	
schKeyword	string	
