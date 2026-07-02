Bizmoney
Resource representations
{
    "bizmoney": long,
    "budgetLock": boolean,
    "customerId": long,
    "refundLock": boolean
}

Property name	Data type	Description
bizmoney	long	
the balance of bizmoney

budgetLock	boolean	
the value which indicates a lock for budget

customerId	long	
The unique ID of the customer

refundLock	boolean	
the value which indicates a lock for refund


Methods
get
GET /billing/bizmoney
Returns amount of bizmoney and a status of locks.

get(charge)
GET /billing/bizmoney/histories/charge?searchStartDt,searchEndDt
bizmoney charging history

get(exhaust)
GET /billing/bizmoney/histories/exhaust?searchStartDt,searchEndDt
bizmoney deduction history

get(period)
GET /billing/bizmoney/histories/period?searchStartDt,searchEndDt
Daily BizMoney Status

Bizmoney: get
Returns amount of bizmoney and a status of locks.

Request
HTTP request
GET /billing/bizmoney
Parameters
Parameter name	Data type	Description

Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

Property name	Data type	Description
bizmoney	long	
the balance of bizmoney

budgetLock	boolean	
the value which indicates a lock for budget

customerId	long	
The unique ID of the customer

refundLock	boolean	
the value which indicates a lock for refund


Bizmoney: get(charge)
bizmoney charging history

Request
HTTP request
GET /billing/bizmoney/histories/charge{?searchStartDt,searchEndDt}
Parameters
Parameter name	Data type	Description
Query parameters
searchStartDt	string	
Period start date (KST, YYYYMMDD)

searchEndDt	string	
Period end date (KST, YYYYMMDD)


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

아래 항목이 배열으로 존재합니다.
Property name	Data type	Description
displayCd	long	
Charge type classification code.

displayName	string	
Charge Type Description(Korean).

newNonRefundableAmt	long	
Free chared bizmoney amount.

newRefundableAmt	long	
Purchased bizmoney amount.

statDt	datetime	
unixtimestamp, Used after removing the last 3 digits.

Request
HTTP request
GET /billing/bizmoney/histories/exhaust{?searchStartDt,searchEndDt}
Parameters
Parameter name	Data type	Description
Query parameters
searchStartDt	string	
Period start date (KST, YYYYMMDD)

searchEndDt	string	
Period end date (KST, YYYYMMDD)


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

아래 항목이 배열으로 존재합니다.
Property name	Data type	Description
activityCd	long	
0: BizMoney exhaust(deductions).

campaignTp	long	
1 : 'Powerlink (WEB_SITE)', 2 : 'Shoppping search AD. (Shopping)', 3 : 'Contents search AD', 4 : 'Brand search AD', 6 : 'Small business DA'

customerId	long	
The unique ID of the customer.

prodInfoCd	string	
Search ad product code.

settleDt	datetime	
unixtimestamp, Used after removing the last 3 digits.

useNonrefundableAmt	long	
Used free charged amount, VAT included.

useRefundableAmt	long	
Used Purchased amount, VAT included.

Bizmoney: get(period)
Daily BizMoney Status

Request
HTTP request
GET /billing/bizmoney/histories/period{?searchStartDt,searchEndDt}
Parameters
Parameter name	Data type	Description
Query parameters
searchStartDt	string	
Period start date(KST, YYYYMMDD)

searchEndDt	string	
Period end date(KST, YYYYMMDD)


Response
요청이 성공적으로 수행이되면, Response Body에 아래 구조의 데이터가 반환됩니다. If the request is successful, the Response Body will return data with the structure below.:

아래 항목이 배열으로 존재합니다.
Property name	Data type	Description
addNonRefundableAmt	long	
Free chared bizmoney amount.

addRefundableAmt	long	
Purchased bizmoney amount.

customerId	long	
The unique ID of the customer.

nonRefundableAmt	long	
balance of free charged amount, VAT included.

refundNonRefundableAmt	long	
Refunded to free charged bizmoney amount, VAT included.

refundRefundableAmt	long	
Refunded to purchased bizmoney amount, VAT included.

refundableAmt	long	
balance of Purchased amount, VAT included.

returnRefundableAmt	long	
Amount of refunded by cash or canceled card payment, VAT included, VAT included.

settleDt	datetime	
unixtimestamp, Used after removing the last 3 digits.

useNonRefundableAmt	long	
Used free charged amount, VAT included.

useRefundableAmt	long	
Used Purchased amount, VAT included.

