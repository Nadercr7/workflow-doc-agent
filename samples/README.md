# Sample workflows

Each subfolder is one production-style workflow: a Python pipeline
plus an Excel output. The agent treats the folder as the unit of work.

## revenue_forecast

A monthly revenue forecasting pipeline. Reads 24 months of actuals from
`input_data.csv`, fits a linear trend, projects 6 months forward, and
writes a 3-sheet workbook (Actuals, Forecast, Sensitivity).

Run it once to generate the Excel file before pointing the agent at the
folder:

```powershell
python samples/revenue_forecast/forecast_pipeline.py
```
