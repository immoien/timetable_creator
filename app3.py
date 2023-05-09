import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta
from matplotlib.ticker import FuncFormatter
from collections import defaultdict
import gspread
from google.oauth2 import service_account
from gspread_dataframe import set_with_dataframe

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

def add_prayer_duration(prayer_minutes, duration, date):
    start = pd.to_datetime(date.strftime('%Y-%m-%d') + ' ' + format_minutes_to_time(prayer_minutes, None), format='%Y-%m-%d %H:%M')
    end = start + timedelta(minutes=duration)
    return start, end

def add_jummah_duration(dhuhr_minutes, jummah_duration, date):
    dhuhr_start, dhuhr_end = add_prayer_duration(dhuhr_minutes, 5, date)
    jummah_start = dhuhr_start - timedelta(minutes=jummah_duration // 2)
    jummah_end = dhuhr_start + timedelta(minutes=jummah_duration // 2)
    return jummah_start, jummah_end

def convert_sunrise(sunrise_str):
    try:
        return pd.to_datetime(sunrise_str, format='%I:%M %p').time()
    except ValueError:
        print(f"Invalid sunrise value: {sunrise_str}")
        return None

# Read the CSV file
file_path = 'data.csv'
df = pd.read_csv(file_path)

# Convert date and time columns to datetime format
df['Date'] = pd.to_datetime(df['Date'])

prayer_columns = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
for item in prayer_columns:
    df[item] = pd.to_datetime(df['Date'].dt.date.astype(str) + ' ' + df[item], format='%Y-%m-%d %I:%M %p')
    df[item] = df[item].dt.time.map(time_to_minutes)

# Add prayer timings
prayer_columns = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
prayer_duration = 5
for prayer in prayer_columns:
    df[prayer+'_start'], df[prayer+'_end'] = zip(*df.apply(lambda x: add_prayer_duration(x[prayer], prayer_duration, pd.Timestamp(x.name)), axis=1))
    df[prayer+'_start'] = df[prayer+'_start'].dt.time.map(time_to_minutes)
    df[prayer+'_end'] = df[prayer+'_end'].dt.time.map(time_to_minutes)

# Set the date as the index
df.set_index('Date', inplace=True)

# Add Jummah timings on Fridays
jummah_duration = 120
jummah_start_end = df[df.index.to_series().dt.dayofweek == 4].apply(lambda x: add_jummah_duration(x['Dhuhr'], jummah_duration, pd.Timestamp(x.name)), axis=1)
for idx, (start, end) in jummah_start_end.iteritems():
    df.at[idx, 'Dhuhr_start'] = start.time().hour * 60 + start.time().minute
    df.at[idx, 'Dhuhr_end'] = end.time().hour * 60 + end.time().minute

# Add sleep timings to the DataFrame
df['SleepStart'], df['SleepEnd'] = zip(*df.apply(lambda x: adjust_sleep_time(x.name, x['Fajr'], x['Isha'], 4), axis=1))
df['SleepStart'] = df['SleepStart'].dt.time.map(time_to_minutes)
df['SleepEnd'] = df['SleepEnd'].dt.time.map(time_to_minutes)

# Add nap timings to the DataFrame
df['NapStart'], df['NapEnd'] = zip(*df.apply(lambda x: adjust_nap_time(x.name, x['Dhuhr'], x['Asr'], 1), axis=1))
df['NapStart'] = df['NapStart'].dt.time.map(time_to_minutes)
df['NapEnd'] = df['NapEnd'].dt.time.map(time_to_minutes)

# Fajr
prayer_duration = 5  # 5 minutes for Fajr prayer
max_delay_before_sunrise = 30  # 30 minutes before sunrise

df['Sunrise'] = df['Sunrise'].apply(convert_sunrise).map(lambda x: time_to_minutes(x) if x is not None else None)

time_slot_count = defaultdict(int)
for index, row in df.iterrows():
    fajr_start = row['Fajr_start']
    sunrise = row['Sunrise']
    fajr_end = sunrise - max_delay_before_sunrise - prayer_duration

    for time in range(int(fajr_start), int(fajr_end - prayer_duration + 1)):
        time_slot_count[time] += 1

common_time_slot = max(time_slot_count, key=time_slot_count.get)

for index, row in df.iterrows():
    fajr_start = row['Fajr_start']
    sunrise = row['Sunrise']
    fajr_end = sunrise - max_delay_before_sunrise - prayer_duration

    if common_time_slot >= fajr_start and common_time_slot + prayer_duration <= fajr_end:
        df.at[index, 'Fajr_start'] = common_time_slot
    else:
        fajr_start = min(fajr_start, common_time_slot)
        df.at[index, 'Fajr_start'] = fajr_start

    df.at[index, 'Fajr_end'] = df.at[index, 'Fajr_start'] + prayer_duration
# Fajr end

# Remove the original prayer columns
# df.drop(prayer_columns, axis=1, inplace=True)

# Plot the prayer timings, sunrise, and sleep schedule
fig, ax = plt.subplots(figsize=(20, 10))
activities = ['Fajr_start', 'Fajr_end', 'Sunrise', 'Dhuhr_start', 'Dhuhr_end', 'Asr_start', 'Asr_end', 'Maghrib_start', 'Maghrib_end', 'Isha_start', 'Isha_end', 'SleepStart', 'SleepEnd', 'NapStart', 'NapEnd']

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
# plt.show()

# Create a new DataFrame with the formatted columns
formatted_df = df.copy()

for item in formatted_df.columns:
    if item != 'Sunrise':
        formatted_df[item] = (pd.to_timedelta(formatted_df[item].astype(int), unit='m')
                              .dt.components[['hours', 'minutes']]
                              .apply(lambda x: '{:02d}:{:02d} {}'.format(x[0] % 12 or 12, x[1], 'AM' if x[0] // 12 == 0 else 'PM'), axis=1))
    else:
        formatted_df[item] = (pd.to_timedelta(formatted_df[item].astype(int), unit='m')
                              .dt.components[['hours', 'minutes']]
                              .apply(lambda x: '{:02d}:{:02d}'.format(x[0], x[1]), axis=1))

# Load your credentials from the JSON file
credentials = service_account.Credentials.from_service_account_file('/Users/moien/Desktop/timetable/creds.json')

# Add the required scopes for Google Sheets and Drive
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = credentials.with_scopes(scopes)

# Authenticate and create a gspread client
gc = gspread.authorize(credentials)

# Open an existing Google Sheet by its title or ID
spreadsheet_title = 'Bot: Timetable'

try:
    spreadsheet = gc.open(spreadsheet_title)
except gspread.exceptions.SpreadsheetNotFound:
    spreadsheet = gc.create(spreadsheet_title)
    spreadsheet.share('email_id', perm_type='user', role='writer')


print(f"Google Sheet URL: {spreadsheet.url}")

# Get the first worksheet in the Google Sheet
worksheet = spreadsheet.get_worksheet(0)

# Clear the content of the worksheet before overwriting with the new data
worksheet.clear()

# Keep only the date part and remove the time
formatted_df.index = formatted_df.index.date

# Reset the index to include the 'Date' column in the formatted DataFrame
formatted_df.reset_index(inplace=True)

# Save the DataFrame to the Google Spreadsheet
set_with_dataframe(worksheet, formatted_df)

# Save the formatted DataFrame to a new CSV file
formatted_df.to_csv('plan.csv')
