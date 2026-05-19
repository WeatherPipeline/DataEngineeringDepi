use Weather_DataBase
select	* from weather_day
---drop table WeatherForecast
---CREATE VIEW weather_day AS
---SELECT 
---    id AS ID,
---    city AS City,
---    country AS Country,
---    [timestamp] AS [Timestamp],
---    temperature AS Temperature,
---    humidity AS Humidity,
---    wind_speed AS [Wind Speed],
---    predicted_temperature AS [Predicted Temperature],
---    alert AS Alert,
---    weather_condition AS [Weather Condition],
---
---    DATENAME(WEEKDAY, [timestamp]) AS Day
---FROM WeatherForecast;
