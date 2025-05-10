import os
import pandas as pd
from datetime import datetime
from scipy.stats import linregress
from tikapi import TikAPI, ValidationException, ResponseException
from google.cloud import bigquery

# 🔐 Authentication
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "tiktokanalyticskey.json"

def upload_to_bigquery(df, table_name):
    project_id = "tiktokanalytics-459417"
    dataset_id = "tiktok_data"
    table_id = f"{project_id}.{dataset_id}.{table_name}"

    client = bigquery.Client()
    job_config = bigquery.LoadJobConfig(autodetect=True)
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print(f"✅ Uploaded {len(df)} rows to {table_id}")

# 🗝️ Get TikAPI Key
api_key = os.environ.get("TIKAPI_KEY")
can_scrape = bool(api_key)

# 🧹 Scrape TikTok following list into DataFrame
def scrape_following_df():
    api = TikAPI(api_key)
    all_rows = []

    try:
        response = api.public.followingList(
            secUid="MS4wLjABAAAAboanSl94WMrjvJtHejLumdRGgy9oYuygOQfbC-iVne34BIfjcygpqSH84qsh2XcT"
        )

        while response:
            data = response.json()
            user_list = data.get("userList", [])
            current_date = datetime.now().strftime("%Y-%m-%d")

            for user_data in user_list:
                username = user_data['user']['uniqueId']
                follower_count = user_data['stats']['followerCount']
                all_rows.append({
                    "Username": username,
                    "Date": current_date,
                    "Follower Count": follower_count
                })

            next_cursor = data.get("nextCursor")
            if not next_cursor:
                break

            print(f"Getting next items {next_cursor}")
            response = response.next_items()

        return pd.DataFrame(all_rows)

    except ValidationException as e:
        print("Validation error:", e, e.field)
    except ResponseException as e:
        print("API response error:", e, e.response.status_code)
    return pd.DataFrame()

# 📈 Calculate Daily Difference, Percent Change, Slope, Avg %
def calculate_slope_and_avg_pct(df):
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by=["Username", "Date"])
    df['Daily Difference'] = df.groupby('Username')["Follower Count"].diff().fillna(0)

    df['Daily Percent Change'] = (
        df.groupby('Username')["Follower Count"]
        .pct_change()
        .replace([float('inf'), float('-inf')], None)
        .fillna(0) * 100
    )

    results = []
    for username, group in df.groupby('Username'):
        group = group.sort_values(by='Date')
        x = group['Date'].map(lambda date: date.toordinal())
        y = group['Follower Count']

        slope = linregress(x, y).slope if len(group) > 1 else None
        avg_pct_change = group['Daily Percent Change'].mean()

        results.append({
            'Username': username,
            'Slope': slope,
            'Average Percent Change': avg_pct_change
        })

    return df, pd.DataFrame(results)

# 🏁 Main Execution
if __name__ == "__main__":
    if not can_scrape:
        print("⚠️ No TikAPI key set — skipping.")
    else:
        df_raw = scrape_following_df()

        if df_raw.empty:
            print("⚠️ No data scraped.")
        else:
            df_with_diff, slope_df = calculate_slope_and_avg_pct(df_raw)

            # Upload both raw data and summary stats
            upload_to_bigquery(df_with_diff, table_name="followers")
            upload_to_bigquery(slope_df, table_name="follower_slopes")

            print("✅ Scrape + analysis + upload complete.")

# TEST ONLY: Dummy data to check BigQuery upload
test_df = pd.DataFrame({
    "Username": ["@testuser1", "@testuser2"],
    "Date": [datetime.today().date(), datetime.today().date()],
    "Follower Count": [10000, 12000],
    "Daily Difference": [150, 300],
    "Daily Percent Change": [1.5, 2.6]
})

upload_to_bigquery(test_df, table_name="followers_test")

