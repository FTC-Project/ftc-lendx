# TEC-45: Scoring Service Specification

## Overview

The **Scoring Service** provides an indication of a borrower's
creditworthiness --- i.e., the likelihood that an individual will not
default on their loan instalments.\
This service is a core component of the lending platform and will be
integrated into most borrower decisioning processes.

The generated score can influence parameters such as:\
- Facility limit\
- Interest rate\
- Loan term

The service will consist of two main components:\
1. **Initial Scoring** -- the first score generated when a borrower
signs up.\
2. **Score Reviews** -- subsequent recalculations and adjustments based
on borrower behaviour over time.

------------------------------------------------------------------------

## 1. Initial Score

### Data Source

The initial score will be derived using data obtained via the **Open
Banking API**.\
Transactional data (e.g., income, expenses, and balance trends) will be
analysed and modelled to assess financial behaviour.

### Model Objective

The model will target **"good financial behaviour."**

Example definition:\
\> Total income -- total expenses \> 0 over a defined period

### Model Development

The model will be developed in **Python**, using libraries such as:\
- `scikit-learn`\
- `optbinning`\
- `pytorch`

Supervised learning methods (e.g., logistic regression, support vector
machines, and random forests) will be employed to predict the borrower's
initial score.

**Supervised models are preferred because they:**\
- Produce interpretable and auditable outputs\
- Comply with regulatory requirements regarding model explainability

> Other deep learning models (such as ANNs or XGBoost) are excluded for
> now, as they generally produce less transparent results and may not
> meet audit requirements.

------------------------------------------------------------------------

### Data Flow

1.  Upon user signup, the platform will call the **Open Banking API**.\
2.  Received transactional data will be stored in a database table
    linked to the user profile.\
3.  The data will be transformed via a **Python preprocessing script**.\
4.  The transformed data will be fed into the trained **supervised
    model** to generate a score.\
5.  The script will return:
    -   The predicted score\
    -   The input variables (features) used for the prediction\
6.  These results will be written to a **Score Table**, which includes:
    -   A column for the full payload (input and model metadata)\
    -   A column for the score value\
    -   Audit tracking for all score changes over time

This design supports both **real-time scoring** and **future model
retraining** using historical data.

------------------------------------------------------------------------

## 2. Score Review

### Purpose

The Score Review process enables **dynamic score adjustments** based on
borrower behaviour over time.\
Borrowers can:\
- Improve their score through responsible repayment behaviour\
- Decrease it through missed payments or defaults

### Approach

The **Score Review** mechanism will be **rule-based**, with fixed
adjustments applied according to defined borrower actions.

**Example Rule:**\
- On-time payment: **+2 points**\
- Missed payment: **--20 points**

### Implementation

-   The review process will be implemented as a **Python batch script**,
    executed monthly.\
-   For each borrower, the script will:
    -   Evaluate repayment behaviour against defined rules\
    -   Calculate the score adjustment and reason code\
    -   Write the updated score, reason, and point difference to the
        **Score Table**

These monthly updates ensure that borrower creditworthiness evolves in
alignment with their ongoing performance. All subsequent loans will 
take the latest score in the **Score Table** into account when determining 
affordability.
