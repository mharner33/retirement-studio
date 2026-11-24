# Retirement Studio Overview

This application is to help a user evaluate the current financial status and goals, and assist in planning for retirement.  The primary goal will be to find the optimal plan from a tax/revenue perspective based on the users goals and current status.

## Questions to ask

The app should ask an needed questions such as current age, expected retirement age, wages, expected Social Security payments, pensions and any other account balances or sources of income such as home value, savings accounts etc.  Research best practices on any other questions that should be asked to build a complet plan.

## Desired features 
- The application should pull the latest IRS rules and tax information specifically related to retirement. A time stamp should be kept and rules should be updated every 3 months. The data should be kept as a markdown file with the key rules in the data/ directory.
- The application should have the ability to add a spouse to the planning and re-evalute the financial plan.
- The application should have the ability to extract 401K/IRA/Stock statement data stored in pdf format from the data/ directory.
- Do some modeling around growth of the current portfolio
- Make recommendations for transfer "ladders" such as transferring 401K data to other instruments such as Roth IRA based on tax and income status
- Evaluate tax strategies based on projected income over various time ranges
- Potentially other things in the future such as Medicare/Medicaid recommendations

