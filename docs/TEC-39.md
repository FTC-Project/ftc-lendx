# TEC-39

## Data Mapping

This is an important part of the score modelling process. This will
provide the data required to obtain the initial score. We will obtain
the data from the open banking API and store it in our tables.

The following tables will be required to store the data:\
- **Accounts**\
- **Balances**\
- **Transactions**\
- **Beneficiaries**

------------------------------------------------------------------------

## Table Design

### Accounts

Accounts will contain account information such as account type, open
date, account number, etc.

  ----------------------------------------------------------------------------
  Field                   Type             Description
  ----------------------- ---------------- -----------------------------------
  UserId                  string           Unique ID that links to user table

  AccountId               string           Unique ID for the account

  AccountIdentification   string           Account number / IBAN

  AccountType             string           e.g. Current, Savings, Credit

  AccountSubType          string           Additional classification

  Currency                string           e.g. ZAR, USD

  Nickname                string           Friendly name

  ProductType             string           Product category (e.g. Student,
                                           Platinum)

  Status                  string           Account status (Active, Closed,
                                           etc.)

  OpeningDate             string (date)    Account creation date

  StatusUpdateDateTime    string           When the status last changed
                          (datetime)       

  CreatedAt               string           When the account was written to the
                          (datetime)       DB
  ----------------------------------------------------------------------------

------------------------------------------------------------------------

### Balances

Balances will contain the balances of the borrower's accounts.

  ---------------------------------------------------------------------------
  Field                  Type             Description
  ---------------------- ---------------- -----------------------------------
  BalanceId              string           Auto-generated locally

  AccountId              string           Related account

  CreditDebitIndicator   string           Credit or Debit

  Type                   string           e.g. ClosingBooked,
                                          InterimAvailable

  DateTime               string           Timestamp of balance
                         (datetime)       

  Amount                 decimal          Balance value

  Currency               string           Currency code

  CreditLineType         string           Type of credit line (if applicable)

  CreditLineAmount       decimal          Credit limit amount

  CreatedAt              string           When the account was written to the
                         (datetime)       DB

  UpdatedAt              string           When the balances were updated
                         (datetime)       
  ---------------------------------------------------------------------------

------------------------------------------------------------------------

### Transactions

Transactions will contain all transaction data for a specific account.
This includes all amounts credited and debited.

  ----------------------------------------------------------------------------------
  Field                      Type             Description
  -------------------------- ---------------- --------------------------------------
  TransactionId              string           Unique transaction identifier

  AccountId                  string           Related account

  TransactionReference       string           Reference ID

  StatementReference         string           Related statement reference

  CreditDebitIndicator       string           "Credit" or "Debit"

  Status                     string           Transaction status

  BookingDateTime            string           Booking date
                             (datetime)       

  ValueDateTime              string           Value date
                             (datetime)       

  TransactionInformation     string           Description / narrative

  Amount                     decimal          Transaction amount

  Currency                   string           Transaction currency

  ChargeAmount               decimal          Any fees or charges

  ExchangeRate               string           From CurrencyExchange.ExchangeRate

  SourceCurrency             string           From CurrencyExchange.SourceCurrency

  TargetCurrency             string           From CurrencyExchange.TargetCurrency

  CreditorName               string           From CreditorAccount.Name

  CreditorAccount            string           From CreditorAccount.Identification

  DebtorName                 string           From DebtorAccount.Name

  DebtorAccount              string           From DebtorAccount.Identification

  MerchantName               string           From MerchantDetails.MerchantName

  MerchantCategoryCode       string           From
                                              MerchantDetails.MerchantCategoryCode

  CardSchemeName             string           From CardInstrument.CardSchemeName

  TransactionBalanceType     string           From TransactionBalance.Type

  TransactionBalanceAmount   decimal          From TransactionBalance.Amount.Amount

  CreatedAt                  string           When the account was written to the DB
                             (datetime)       
  ----------------------------------------------------------------------------------

------------------------------------------------------------------------

### Beneficiaries

Beneficiaries will contain all beneficiary information linked to the
borrower's account.

  ------------------------------------------------------------------------
  Field               Type             Description
  ------------------- ---------------- -----------------------------------
  BeneficiaryId       string           Unique beneficiary ID

  AccountId           string           Related account       

  Name                string           Beneficiary name

  Type                string           Beneficiary type

  AccountType         string           Type of account (from
                                       BeneficiaryAccount.Type)
  ------------------------------------------------------------------------
