from tqdm import tqdm
import os
import pandas as pd

from tqdm_logger import TqdmLogger

logger = TqdmLogger("FDSLogger")

DATA_DIR = './data'

def load():
    filenames = os.listdir(DATA_DIR)
    dfs = []
    num_rows_loaded = 0
    prog_bar = tqdm(filenames)
    prog_bar.set_description("Loading files")
    for filename in prog_bar:
        logger.info(f"+Loading {filename} ({num_rows_loaded} rows loaded)")
        _, city, year = filename[:-4].split("_")
        df = pd.read_csv(f"{DATA_DIR}/{filename}", index_col=0)
        df = df.dropna(axis=0)
        df["CITY"] = city
        df["YEAR"] = int(year)
        num_rows_loaded += df.shape[0]
        dfs.append(df)
        logger.info(f"-Loading {filename} ({num_rows_loaded} rows loaded)")

    return dfs

def main():
    dfs = load()
    logger.info("+Concatenating data")
    merged_df = pd.concat(dfs)
    logger.info("-Concatenating data")
    logger.info("+Saving data")
    merged_df.to_csv("merged.csv")
    logger.info("-Saving data")


if __name__ == "__main__":
    main()
