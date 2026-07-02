MasterReport
Methods
list
GET /master-reports
Get all list of "Master Report" Jobs LIST (maximum 100 jobs) which recently created

get (by id)
GET /master-reports/id
Get a "Master Report" Job details by specific ID.

create
POST /master-reports
Create "Master Report" job

delete all
DELETE /master-reports
Delete all "Master Report" jobs.

delete (by id)
DELETE /master-reports/id
Delete by "Master Report" job id.



MasterReport: list
Get all list of "Master Report" Jobs LIST (maximum 100 jobs) which recently created

Request
HTTP request
GET /master-reports
Parameters
Parameter name	Data type	Description

Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

아래 항목이 배열으로 존재합니다.
Property name	Data type	Description
id	string	
Master Report Job id.

item	string	
Master Report Item. Campaign, Campaign Budget, Business Channel, Ad group, Ad group Budget, Ad Keyword, Ad(creative), Ad Extension, Qi grade, Label, LabelRef, Media info.


item의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the item.Valid items are:

Campaign
CampaignBudget
BusinessChannel
Adgroup
AdgroupBudget
Keyword
Ad
AdExtension
Qi
Label
LabelRef
Media
Biz
SeasonalEvent
ShoppingProduct
ContentsAd
PlaceAd
CatalogAd
AdQi
ProductGroup
ProductGroupRel
BrandAd
BrandThumbnailAd
BrandBannerAd
Criterion
SharedBudget
Asset
AdAssetLink
RsaAd
HospitalAd
fromTime	string	
The time at which the "Delta"(entity changed during a specific period of time) starts (ISO 8601 UTC)

updateTime	string	
Time of report generation (ISO 8601 UTC)

status	string	
Job status., REGIST, RUNNING, BUILT, NONE, ERROR


status의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the status.Valid items are:

REGIST
RUNNING
BUILT
NONE
ERROR
downloadUrl	string	
Address of a report file.

MasterReport: get (by id)
Get a "Master Report" Job details by specific ID.

Request
HTTP request
GET /master-reports/{id}
Parameters
Parameter name	Data type	Description
Path parameters
id	string	
Valid Master Report Job Id.


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
id	string	
Master Report Job id.

item	string	
Master Report Item. Campaign, Campaign Budget, Business Channel, Ad group, Ad group Budget, Ad Keyword, Ad(creative), Ad Extension, Qi grade, Label, LabelRef, Media info.


item의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the item.Valid items are:

Campaign
CampaignBudget
BusinessChannel
Adgroup
AdgroupBudget
Keyword
Ad
AdExtension
Qi
Label
LabelRef
Media
Biz
SeasonalEvent
ShoppingProduct
ContentsAd
PlaceAd
CatalogAd
AdQi
ProductGroup
ProductGroupRel
BrandAd
BrandThumbnailAd
BrandBannerAd
Criterion
SharedBudget
Asset
AdAssetLink
RsaAd
HospitalAd
fromTime	string	
The time at which the "Delta"(entity changed during a specific period of time) starts (ISO 8601 UTC)

updateTime	string	
Time of report generation (ISO 8601 UTC)

status	string	
Job status., REGIST, RUNNING, BUILT, NONE, ERROR


status의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the status.Valid items are:

REGIST
RUNNING
BUILT
NONE
ERROR
downloadUrl	string	
Address of a report file.

MasterReport: create
Create "Master Report" job

Request
HTTP request
POST /master-reports
Parameters
Parameter name	Data type	Description
Request body
item	string	Required
Master Report Item. Campaign, Campaign Budget, Business Channel, Ad group, Ad group Budget, Ad Keyword, Ad(creative), Ad Extension, Qi grade, Label, LabelRef, Media info.


item의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the item.Valid items are:

Campaign
CampaignBudget
BusinessChannel
Adgroup
AdgroupBudget
Keyword
Ad
AdExtension
Qi
Label
LabelRef
Media
Biz
SeasonalEvent
ShoppingProduct
ContentsAd
PlaceAd
CatalogAd
AdQi
ProductGroup
ProductGroupRel
BrandAd
BrandThumbnailAd
BrandBannerAd
Criterion
SharedBudget
Asset
AdAssetLink
RsaAd
HospitalAd
fromTime	string	
The time at which the "Delta"(entity changed during a specific period of time) starts (ISO 8601 UTC)


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
id	string	
Master Report Job id.

item	string	
Master Report Item. Campaign, Campaign Budget, Business Channel, Ad group, Ad group Budget, Ad Keyword, Ad(creative), Ad Extension, Qi grade, Label, LabelRef, Media info.


item의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the item.Valid items are:

Campaign
CampaignBudget
BusinessChannel
Adgroup
AdgroupBudget
Keyword
Ad
AdExtension
Qi
Label
LabelRef
Media
Biz
SeasonalEvent
ShoppingProduct
ContentsAd
PlaceAd
CatalogAd
AdQi
ProductGroup
ProductGroupRel
BrandAd
BrandThumbnailAd
BrandBannerAd
Criterion
SharedBudget
Asset
AdAssetLink
RsaAd
HospitalAd
fromTime	string	
The time at which the "Delta"(entity changed during a specific period of time) starts (ISO 8601 UTC)

updateTime	string	
Time of report generation (ISO 8601 UTC)

status	string	
Job status., REGIST, RUNNING, BUILT, NONE, ERROR


status의 종류입니다. 유효한 값 목록은 다음과 같습니다.
The type of the status.Valid items are:

REGIST
RUNNING
BUILT
NONE
ERROR
downloadUrl	string	
Address of a report file.

MasterReport: delete all
Delete all "Master Report" jobs.

Request
HTTP request
DELETE /master-reports
Parameters
Parameter name	Data type	Description

Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description

MasterReport: delete (by id)
Delete by "Master Report" job id.

Request
HTTP request
DELETE /master-reports/{id}
Parameters
Parameter name	Data type	Description
Path parameters
id	string	
Valid Master Report Job Id


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
