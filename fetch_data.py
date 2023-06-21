from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import os
import pandas as pd
import queue
import requests
import time
import threading

from tqdm_logger import TqdmLogger

logger = TqdmLogger("FDSLogger")


MAX_OUTSTANDING_REQUESTS = 12  # Throttle network requests
MAX_QUEUE_SIZE           = 16  # Manage memory usage
OUTPUT_DIR               = "./data"

top_cities_ep = "https://h1bdata.info/topcities.php"
query_ep      = "https://h1bdata.info/index.php?year={year}&city={city}"
make_query_ep = lambda city, year: query_ep.format(year=year, city="+".join(city.lower().split()))
format_index  = lambda idx: (4 - len(str(idx))) * "0" + str(idx)


def extract_from_filename(filename):
    filename = filename[:-4]
    splitname = filename.split('_')
    city = ' '.join(splitname[1:-1])
    year = splitname[-1]
    return city.strip(), int(year.strip())

def make_filename(idx, city, year):
    idx = (4 - len(str(idx))) * "0" + str(idx)
    return f"{idx}_{city.replace(' ' , '-')}_{year}.csv"

def safe_get(session, endpoint, *args, **kwargs):
    logger.info(f"+Fetching {endpoint}...")
    try:
        return session.get(endpoint, *args, **kwargs)
    except Exception as e:
        logger.error(f"Failed to get {endpoint}: {e}")
    finally:
        logger.info(f"-Fetching {endpoint}...")

def fetch_data(cities, years, existing, all_done_event, output_queue):
    futures = {}
    session = requests.Session()
    session.headers['User-Agent'] = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 '
                                     '(KHTML, like Gecko) Chrome/34.0.1847.131 Safari/537.36')

    total_count = len(cities) * len(years)
    with ThreadPoolExecutor(MAX_OUTSTANDING_REQUESTS) as pool, \
         tqdm(total=total_count) as prog_bar:
        for i, city in enumerate(cities, 1):
            for year in years:
                while len(futures) == MAX_OUTSTANDING_REQUESTS:
                    # Wait for completed requests
                    for future in as_completed(futures):
                        i_response, city_response, year_response = futures[future]
                        response = future.result()
                        if response is not None:
                            html     = response.text
                            message  = (i_response, city_response, year_response, html)
                            output_queue.put(message)

                        prog_bar.update(1)
                        del futures[future]
                        break

                # Push a new request
                if (city, year) in existing:
                    prog_bar.update(1)
                    continue

                future = pool.submit(safe_get, session, make_query_ep(city, year))
                futures[future] = (i, city, year)
                time.sleep(0.2)

        # Remaining requests
        for future in as_completed(futures):
            i_response, city_response, year_response = futures[future]
            response = future.result()
            if response is not None:
                html     = response.text
                message  = (i_response, city_response, year_response, html)
                output_queue.put(message)

            prog_bar.update(1)

    logger.info("fetch_data() all done")
    all_done_event.set()

def parse_and_save(all_done_event, input_queue):
    while not input_queue.empty() or not all_done_event.is_set():
        try:
            i, city, year, html = input_queue.get(timeout=5)
        except queue.Empty:
            continue

        logger.info(f"+Processing for {city} in year {year}...")
        try:
            dfs = pd.read_html(html)
        except ValueError as e:
            logger.info(f"WARNING: No tables found for {city} in year {year}.")

        if len(dfs) > 1:
            raise ValueError(f"Read {len(html)} dataframes for {city} in year {year} instead of 1.")

        df = dfs[0]
        df = df[[col for col in df.columns if "Unnamed" not in col]]
        df = df[~df["START DATE"].fillna("1970-01-01").str.contains("adsbygoogle")]
        df = df.dropna(axis=0)
        filename = make_filename(i, city, year)
        df.to_csv(os.path.join(OUTPUT_DIR, filename))
        logger.info(f"-Processing for {city} in year {year}...")

    logger.info("parse_and_save() all done")

def main():
    # Fetch the top cities
    top_cities_response = requests.get(top_cities_ep)
    top_cities_html     = top_cities_response.text
    top_cities_dfs = pd.read_html(top_cities_html)
    if len(top_cities_dfs) != 1:
        raise ValueError(f"Read {len(top_cities_dfs)} dataframes from {top_cities_ep} instead of 1.")
    top_cities_df = top_cities_dfs[0]
    top_cities_df = top_cities_df[top_cities_df["City Name"].str.len() < 50]
    top_cities_df = top_cities_df[~top_cities_df["City Name"].str.contains('â')]

    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)

    cities   = top_cities_df["City Name"].values
    years    = range(2012, 2023)
    existing_data_files = (f for f in os.listdir(OUTPUT_DIR) if f[-4:] == ".csv")
    existing = set(map(extract_from_filename, existing_data_files))

    html_queue     = queue.Queue(maxsize=MAX_QUEUE_SIZE)
    all_done_event = threading.Event()

    fetch_data_thread = threading.Thread(
        target=fetch_data,
        args=(cities, years, existing, all_done_event, html_queue),
        daemon=True
    )
    parse_and_save_thread = threading.Thread(
        target=parse_and_save,
        args=(all_done_event, html_queue),
        daemon=True
    )

    fetch_data_thread.start()
    parse_and_save_thread.start()

    # joining prevents SIGTERM somehow
    while True:
        time.sleep(3)
        if not fetch_data_thread.is_alive() and not parse_and_save_thread.is_alive():
            break

if __name__ == "__main__":
    main()
