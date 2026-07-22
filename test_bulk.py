import time
import requests
import datetime
import pandas as pd
from io import StringIO
from data_provider import _get_nse_session

def fetch_bulk_deals():
    session = _get_nse_session()
    to_date = datetime.datetime.now().strftime("%d-%m-%Y")
    from_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/historical/bulk-deals?symbol=&from={from_date}&to={to_date}&csv=true"
    
    response = session.get(url, timeout=5)
    response.raise_for_status()
    
    # NSE returns CSV text with this URL when csv=true
    df = pd.read_csv(StringIO(response.text))
    return df

if __name__ == "__main__":
    t1 = time.time()
    try:
        df = fetch_bulk_deals()
        print(f"Success! {len(df)} rows found in {time.time()-t1:.2f}s")
        print(df.head(2))
    except Exception as e:
        print(f"Error: {e}")
