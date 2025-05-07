import os
import pandas as pd
from scipy.stats import linregress
from tikapi import TikAPI, ValidationException, ResponseException
from openpyxl import Workbook, load_workbook
from datetime import datetime

# Load TikAPI key from environment variable
api_key = os.environ.get("TIKAPI_KEY")
if not api_key:
    raise ValueError("TIKAPI_KEY environment variable is not set")

api = TikAPI(api_key)

# File paths (relative to current directory)
base_file = "shortlist_data.xlsx"

# Function to fetch TikTok following list and save to Excel
def scrape_following_to_excel(excel_file):
    shortlist = []

    try:
        response = api.public.followingList(
            secUid="MS4wLjABAAAAboanSl94WMrjvJtHejLumdRGgy9oYuygOQfbC-iVne34BIfjcygpqSH84qsh2XcT"
        )

        try:
            workbook = load_workbook(excel_file)
            sheet = workbook.active
        except FileNotFoundError:
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["Username", "Date", "Follower Count"])

        while response:
            data = response.json()
            user_list = data.get("userList", [])
            current_date = datetime.now().strftime("%Y-%m-%d")

            for user_data in user_list:
                username = user_data['user']['uniqueId']
                follower_count = user_data['stats']['followerCount']
                shortlist.append(username)
                sheet.append([username, current_date, follower_count])

            workbook.save(excel_file)

            next_cursor = data.get("nextCursor")
            if not next_cursor:
                break

            print(f"Getting next items {next_cursor}")
            response = response.next_items()

        print(shortlist)

    except ValidationException as e:
        print("Validation error:", e, e.field)
    except ResponseException as e:
        print("API response error:", e, e.response.status_code)

# Function to calculate follower growth stats
def calculate_slopes_with_current_followers(input_file, output_file):
    excel_data = pd.ExcelFile(input_file)
    sheet_name = excel_data.sheet_names[0]
    data = excel_data.parse(sheet_name)

    data['Date'] = pd.to_datetime(data['Date'])
    data = data.sort_values(by=['Username', 'Date'])
    data['Daily Difference'] = data.groupby('Username')['Follower Count'].diff().fillna(0)

    results = []
    for username, group in data.groupby('Username'):
        group = group.sort_values(by='Date')
        x = group['Date'].map(lambda date: date.toordinal())
        y = group['Follower Count']

        slope = linregress(x, y).slope if len(group) > 1 else None
        pct_changes = group['Follower Count'].pct_change().dropna()
        valid_pct_changes = pct_changes[~pct_changes.isin([float('inf'), float('-inf')])]
        avg_pct_change = valid_pct_changes.mean() if not valid_pct_changes.empty else None

        results.append({
            'Username': username,
            'Slope': slope,
            'Average Percent Change': avg_pct_change
        })

    slope_data = pd.DataFrame(results)

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        data.to_excel(writer, index=False, sheet_name=sheet_name)
        slope_data.to_excel(writer, index=False, sheet_name='Slopes')


# Run if script is executed directly
if __name__ == "__main__":
    today = datetime.today().strftime('%m.%d.%y')

    updated_file = f"shortlist_data_updated{today}.xlsx"
    slope_file = f"shortlist_data_slope{today}.xlsx"

    scrape_following_to_excel(base_file)

    df = pd.read_excel(base_file)
    df = df.sort_values(by=["Username", "Date"])
    df['Daily Difference'] = df.groupby('Username')["Follower Count"].diff().fillna(0)
    df.to_excel(updated_file, index=False)

    calculate_slopes_with_current_followers(updated_file, slope_file)

    print(f"Updated data saved to {updated_file}")
    print(f"Slope analysis saved to {slope_file}")
    print("Done.")
