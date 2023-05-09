import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta
from matplotlib.ticker import FuncFormatter

def time_to_minutes(time_obj):
    return time_obj.hour * 60 + time_obj.minute

def format_minutes_to_time(x, pos):
    hours = int(x // 60)
    minutes = int(x % 60)
    return f'{hours:02d}:{minutes:02d}'

def adjust_sleep_time(date, fajr_minutes, isha_minutes, sleep_duration):
    fajr = pd.to_datetime(date.strftime('%Y-%m-%d') + ' ' + format_minutes_to_time(fajr_minutes, None), format='%Y-%m-%d %H:%M')
    isha = pd.to_datetime(date.strftime('%Y-%m-%d') + ' ' + format_minutes_to_time(isha_minutes, None), format='%Y-%m-%d %H:%M')
    
    preferred_sleep_start = pd.to_datetime(date.strftime('%Y-%m-%d') + ' 00:00:00')
    # preferred_sleep_end = preferred_sleep_start + timedelta(hours=sleep_duration)

    if isha < preferred_sleep_start:
        sleep_start = preferred_sleep_start
    else:
        sleep_start = isha + timedelta(minutes=30)

    sleep_end = sleep_start + timedelta(hours=sleep_duration)

    if sleep_end > fajr:
        sleep_end = fajr
        sleep_start = sleep_end - timedelta(hours=sleep_duration)

    buffer = timedelta(minutes=30)
    if preferred_sleep_start < sleep_start - buffer:
        sleep_start = preferred_sleep_start
        sleep_end = sleep_start + timedelta(hours=sleep_duration)
        if sleep_end > fajr:
            sleep_end = fajr
            sleep_start = sleep_end - timedelta(hours=sleep_duration)

    return sleep_start, sleep_end


def adjust_nap_time(date, dhuhr_minutes, asr_minutes, nap_duration):
    dhuhr = pd.to_datetime(date.strftime('%Y-%m-%d') + ' ' + format_minutes_to_time(dhuhr_minutes, None), format='%Y-%m-%d %H:%M')
    asr = pd.to_datetime(date.strftime('%Y-%m-%d') + ' ' + format_minutes_to_time(asr_minutes, None), format='%Y-%m-%d %H:%M')
    
    preferred_nap_start = pd.to_datetime(date.strftime('%Y-%m-%d') + ' 13:00', format='%Y-%m-%d %H:%M')
    preferred_nap_end = pd.to_datetime(date.strftime('%Y-%m-%d') + ' 14:00', format='%Y-%m-%d %H:%M')
    
    if preferred_nap_start >= dhuhr + timedelta(minutes=30) and preferred_nap_end <= asr - timedelta(minutes=30):
        nap_start = preferred_nap_start
        nap_end = preferred_nap_end
    else:
        nap_start = dhuhr + timedelta(minutes=30)
        time_until_asr = (asr - nap_start).seconds / 3600
        
        if time_until_asr >= nap_duration:
            nap_end = nap_start + timedelta(hours=nap_duration)
        else:
            nap_end = asr - timedelta(minutes=30)
    return nap_start, nap_end

# Read the CSV file
file_path = 'data.csv'
df = pd.read_csv(file_path)

# Convert date and time columns to datetime format
df['Date'] = pd.to_datetime(df['Date'])
for item in ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
    df[item] = pd.to_datetime(df['Date'].dt.date.astype(str) + ' ' + df[item], format='%Y-%m-%d %I:%M %p')
    df[item] = df[item].dt.time.map(time_to_minutes)

# Set the date as the index
df.set_index('Date', inplace=True)

# Add sleep timings to the DataFrame
df['SleepStart'], df['SleepEnd'] = zip(*df.apply(lambda x: adjust_sleep_time(x.name, x['Fajr'], x['Isha'], 4), axis=1))
df['SleepStart'] = df['SleepStart'].dt.time.map(time_to_minutes)
df['SleepEnd'] = df['SleepEnd'].dt.time.map(time_to_minutes)

# Add nap timings to the DataFrame
df['NapStart'], df['NapEnd'] = zip(*df.apply(lambda x: adjust_nap_time(x.name, x['Dhuhr'], x['Asr'], 1), axis=1))
df['NapStart'] = df['NapStart'].dt.time.map(time_to_minutes)
df['NapEnd'] = df['NapEnd'].dt.time.map(time_to_minutes)

# Plot the prayer timings, sunrise, and sleep schedule
fig, ax = plt.subplots(figsize=(20, 10))
activities = ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha', 'SleepStart', 'SleepEnd', 'NapStart', 'NapEnd']
for activity in activities:
    line, = ax.plot(df.index, df[activity], label=activity, marker='o', markersize=8, alpha=0.8)

# Configure the x-axis with date format
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

# Set chart title, labels, and legend
ax.set_title('Namaz Timings, Sunrise, and Sleep Schedule in Lodz, Poland')
ax.set_xlabel('Date')
ax.set_ylabel('Time (minutes since midnight)')
ax.legend()

# Format y-axis to display time in hours and minutes
ax.yaxis.set_major_formatter(FuncFormatter(format_minutes_to_time))

# Show the chart
plt.show()

# Create a new DataFrame with the formatted columns
formatted_df = df.copy()

# Format the time columns
for item in ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha', 'SleepStart', 'SleepEnd', 'NapStart', 'NapEnd']:
    formatted_df[item] = pd.to_datetime(formatted_df[item], unit='m').dt.strftime('%I:%M %p')

# Save the formatted DataFrame to a new CSV file
formatted_df.to_csv('plan.csv')
