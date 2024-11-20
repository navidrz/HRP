# %%
# =================================
# Hierarchical Risk Parity - CVaR (Revised)
# =================================

"""
This script implements Hierarchical Risk Parity (HRP) optimization using the `skfolio` library.
It fetches portfolio symbol prices from an API, loads Market Index, Market Cap, USD to Rial Exchange Rate,
and Risk-Free Rate data from user-selected files, processes the data, trains multiple optimization models,
and evaluates their performance.

Key Features:
1. **Tkinter File Browsing**: Users can select Market Index, Market Cap, USD to Rial Exchange Rate, and Risk-Free Rate data files.
2. **User Input for Symbol IDs**: Users input symbol IDs via the console.
3. **Data Fetching and Loading**: Asynchronously fetches symbol data and loads external data files with fuzzy column matching.
4. **Data Preprocessing**: Aligns data, computes returns, scores overlaps, and splits into training and testing sets.
5. **Model Implementation**: Trains multiple optimization models with different configurations, including `HierarchicalRiskParity` and `DistributionallyRobustCVaR`.
6. **Evaluation**: Analyzes risk contributions, plots cumulative returns and portfolio compositions, and prints summary statistics.
7. **Data Overlap Scoring**: Scores and counts overlapping dates to inform the user about data alignment.
8. **Exporting Portfolio Weights**: Exports the optimized portfolios with their weights to CSV and Excel files.
9. **Ranking Portfolios**: Ranks portfolios based on the Annualized Sharpe Ratio.

Ensure that your data files are correctly formatted with the necessary columns before running the script.
"""

# %%
# Import Necessary Libraries
# ==========================
import asyncio
import logging
from datetime import datetime
from tkinter import Tk, filedialog
import sys

import jdatetime  # For Jalali date handling
import pandas as pd
from fuzzywuzzy import fuzz, process
from plotly.io import show
from sklearn.model_selection import train_test_split
from tsetmc_api.symbol import Symbol  # Ensure this is the correct import for the Symbol class

from skfolio import Population, RiskMeasure
from skfolio.cluster import HierarchicalClustering, LinkageMethod
from skfolio.distance import KendallDistance
from skfolio.optimization import EqualWeighted, HierarchicalRiskParity, DistributionallyRobustCVaR
from skfolio.prior import FactorModel

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# %%
# DataFetcher Class
# =================
class DataFetcher:
    """Class responsible for fetching and processing data from the API."""

    @staticmethod
    async def fetch_daily_history(symbol_id: str) -> pd.DataFrame:
        """
        Fetches the daily history of a symbol asynchronously with logging and error handling.
        Converts dates from Jalali to Gregorian if necessary.

        Parameters:
        -----------
        symbol_id : str
            The unique identifier for the symbol.

        Returns:
        --------
        pd.DataFrame
            DataFrame containing 'date', 'close', 'volume', 'value' columns.
        """
        try:
            logger.info(f"Start fetching daily history for symbol_id: {symbol_id}")
            symbol = Symbol(symbol_id=symbol_id)
            daily_history = await symbol.get_daily_history_async()

            if not daily_history:
                logger.warning(f"No daily history data retrieved for symbol_id: {symbol_id}")
                return pd.DataFrame()

            stock_data = []
            for row in daily_history:
                try:
                    # Convert Jalali dates to Gregorian if necessary
                    if isinstance(row.date, jdatetime.date):
                        gregorian_date = pd.to_datetime(row.date.togregorian()).normalize()
                    elif isinstance(row.date, datetime):
                        gregorian_date = pd.to_datetime(row.date).normalize()
                    else:
                        gregorian_date = pd.NaT
                        logger.warning(f"Unknown date format for row: {row}")

                    stock_data.append({
                        'date': gregorian_date,
                        'close': row.close,
                        'volume': row.volume,
                        'value': row.value
                    })
                except Exception as e:
                    logger.warning(f"Skipping invalid date value: {row.date} - {e}")

            stock_df = pd.DataFrame(stock_data).dropna(subset=['date'])
            stock_df = stock_df.sort_values('date').drop_duplicates(subset='date')  # Remove duplicate dates
            stock_df['close'] = pd.to_numeric(stock_df['close'], errors='coerce')
            stock_df = stock_df.dropna(subset=['close'])
            logger.info(f"Successfully fetched and converted daily history for symbol_id: {symbol_id}")
            if not stock_df.empty:
                logger.info(f"Date Range for symbol_id {symbol_id}: {stock_df['date'].min()} to {stock_df['date'].max()}")
            return stock_df
        except Exception as e:
            logger.error(f"Error fetching daily history for symbol_id: {symbol_id} - {e}")
            return pd.DataFrame()

    @staticmethod
    async def fetch_all_symbols(symbol_ids: list) -> dict:
        """
        Fetches daily history data for all symbols asynchronously.

        Parameters:
        -----------
        symbol_ids : list
            List of symbol IDs to fetch data for.

        Returns:
        --------
        dict
            Dictionary mapping symbol IDs to their fetched DataFrames.
        """
        tasks = [DataFetcher.fetch_daily_history(symbol_id) for symbol_id in symbol_ids]
        results = await asyncio.gather(*tasks)
        return dict(zip(symbol_ids, results))

# %%
# DataLoader Class
# ================
class DataLoader:
    """Class responsible for loading and processing external data files."""

    @staticmethod
    def load_data(file_type: str) -> pd.DataFrame:
        """
        Opens a file dialog for the user to select an Excel or CSV file containing the required data.
        Automatically identifies required columns using fuzzy matching.

        Parameters:
        -----------
        file_type : str
            Type of data to load ('market', 'risk_free_rate', 'market_cap', 'usd_to_rial').

        Returns:
        --------
        pd.DataFrame
            Loaded and processed DataFrame with standardized column names.
        """
        try:
            # Open file dialog to select the Excel or CSV file
            root = Tk()
            root.withdraw()  # Hide the root window
            if file_type == 'market':
                title = "Select Market Index Data File"
            elif file_type == 'risk_free_rate':
                title = "Select Risk-Free Rate Data File"
            elif file_type == 'market_cap':
                title = "Select Market Cap in USD Data File"
            elif file_type == 'usd_to_rial':
                title = "Select USD to Rial Exchange Rate Data File"
            else:
                logger.error("Invalid file type specified.")
                return pd.DataFrame()

            filepath = filedialog.askopenfilename(
                title=title,
                filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv")]
            )
            root.destroy()  # Close the tkinter root window

            if not filepath:
                logger.error("No file selected.")
                return pd.DataFrame()

            if filepath.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(filepath, index_col=None)
            elif filepath.lower().endswith('.csv'):
                df = pd.read_csv(filepath, index_col=None)
            else:
                logger.error("Unsupported file format selected.")
                return pd.DataFrame()

            logger.info(f"Loading {file_type} data from {filepath}")

            # Define required fields based on file type
            required_fields = {}
            if file_type == 'market':
                required_fields = {
                    'date': ['date', 'Date', 'Gregorian Date', 'تاریخ میلادی'],
                    'daily_return': ['return', 'daily return', 'بازده', 'بازده روزانه'],
                }
            elif file_type == 'risk_free_rate':
                required_fields = {
                    'date': ['date', 'Date', 'Gregorian Date', 'تاریخ میلادی'],
                    'risk_free_rate': ['ytm', 'YTM', 'Yield to Maturity', 'Interest Rate', 'Risk-Free Rate'],
                }
            elif file_type == 'market_cap':
                required_fields = {
                    'date': ['date', 'Date', 'Gregorian Date', 'تاریخ میلادی'],
                    'market_cap': ['market_cap', 'Market Cap', 'Market Capitalization', 'بازار سرمایه', 'price'],
                }
            elif file_type == 'usd_to_rial':
                required_fields = {
                    'date': ['date', 'Date', 'Gregorian Date', 'تاریخ میلادی'],
                    'usd_to_rial': ['usd_to_rial', 'USD to Rial', 'Exchange Rate', 'نرخ تبدیل دلار به ریال', 'price'],
                }

            # Normalize column names
            normalized_columns = {col.strip().lower(): col for col in df.columns}
            mapped_columns = {}

            for field, possible_names in required_fields.items():
                # Attempt to find the best match for the field
                best_match, score = process.extractOne(field, list(normalized_columns.keys()), scorer=fuzz.token_sort_ratio)
                if score >= 80:
                    original_col = normalized_columns[best_match]
                    mapped_columns[field] = original_col
                    logger.info(f"Mapped '{field}' to column '{original_col}' with score {score}")
                else:
                    # Try alternative names
                    best_alt_match = None
                    best_alt_score = 0
                    for alt_name in possible_names:
                        alt_name_normalized = alt_name.strip().lower()
                        match, alt_score = process.extractOne(
                            query=alt_name_normalized,
                            choices=list(normalized_columns.keys()),
                            scorer=fuzz.token_sort_ratio
                        )
                        if alt_score > best_alt_score and alt_score >= 80:
                            best_alt_match = normalized_columns.get(match)
                            best_alt_score = alt_score
                    if best_alt_match:
                        mapped_columns[field] = best_alt_match
                        logger.info(f"Mapped '{field}' to column '{best_alt_match}' with score {best_alt_score}")
                    else:
                        logger.error(f"Required column for '{field}' not found in {file_type} data.")
                        return pd.DataFrame()

            # Rename columns to standardized names
            rename_mapping = {mapped_columns[field]: field for field in required_fields}
            df = df.rename(columns=rename_mapping)

            # Convert 'date' column to datetime and normalize to remove time components
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.normalize()
            df = df.dropna(subset=['date'])
            df = df.sort_values('date').drop_duplicates(subset='date')  # Remove duplicate dates

            # Log the date range
            start_date = df['date'].min()
            end_date = df['date'].max()
            logger.info(f"{file_type.capitalize()} Data Date Range: {start_date} to {end_date}")

            # For numeric columns, ensure correct data types
            numeric_fields = [field for field in required_fields if field != 'date']
            for field in numeric_fields:
                df[field] = pd.to_numeric(df[field], errors='coerce')

            df = df.dropna(subset=numeric_fields)  # Drop rows with NaNs in required numeric fields
            logger.info(f"Successfully loaded and processed {file_type} data.")
            return df
        except Exception as e:
            logger.error(f"Error data loader: {e}")
            return pd.DataFrame()

    @staticmethod
    def load_multiple_files(file_types: list) -> dict:
        """
        Loads multiple data files based on the provided file types.

        Parameters:
        -----------
        file_types : list
            List of file types to load.

        Returns:
        --------
        dict
            Dictionary mapping file types to their respective DataFrames.
        """
        data = {}
        for file_type in file_types:
            logger.info(f"Loading data for file type: {file_type}")
            df = DataLoader.load_data(file_type)
            if df.empty:
                logger.error(f"Failed to load data for file type: {file_type}")
                sys.exit(1)
            data[file_type] = df
        return data

# %%
# Preprocessor Class
# ==================
class Preprocessor:
    """Handles data preprocessing steps such as calculating returns and aligning datasets."""

    @staticmethod
    def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates daily returns from price data.

        Parameters:
        -----------
        prices : pd.DataFrame
            DataFrame containing daily closing prices for each stock.

        Returns:
        --------
        pd.DataFrame
            DataFrame containing daily returns.
        """
        try:
            returns = prices.pct_change().dropna()
            logger.info("Calculated daily returns from price data.")
            return returns
        except Exception as e:
            logger.error(f"Error calculating returns: {e}")
            return pd.DataFrame()

    @staticmethod
    def align_datasets(*datasets: pd.DataFrame) -> pd.DataFrame:
        """
        Aligns multiple datasets on their date indices.

        Parameters:
        -----------
        datasets : pd.DataFrame
            Variable number of DataFrames to align.

        Returns:
        --------
        pd.DataFrame
            Combined DataFrame with aligned dates.
        """
        try:
            # Log date ranges and sample dates for each dataset
            for i, df in enumerate(datasets):
                if isinstance(df, pd.Series):
                    logger.info(f"Dataset {i}: {df.name} Date Range: {df.index.min()} to {df.index.max()}")
                else:
                    logger.info(f"Dataset {i}: Date Range: {df.index.min()} to {df.index.max()}")
                    # Log sample dates
                    sample_dates = df.index[:5].tolist()
                    logger.info(f"Dataset {i} sample dates: {sample_dates}")

            # Find intersection of all date indices
            common_dates = datasets[0].index
            for df in datasets[1:]:
                common_dates = common_dates.intersection(df.index)

            logger.info(f"Number of common dates after intersection: {len(common_dates)}")

            if len(common_dates) == 0:
                logger.error("No overlapping dates found across datasets after intersection.")
                return pd.DataFrame()

            # Align datasets on the common dates
            combined = pd.concat([df.loc[common_dates] for df in datasets], axis=1)
            combined = combined.dropna()
            logger.info(f"Number of dates after dropna: {len(combined)}")
            logger.info(f"Number of common dates after alignment: {len(combined)}")
            return combined
        except Exception as e:
            logger.error(f"Error aligning datasets: {e}")
            return pd.DataFrame()

    @staticmethod
    def process_data(prices: pd.DataFrame, market_returns: pd.Series, risk_free_rate: pd.Series,
                    market_cap: pd.Series, usd_to_rial: pd.Series) -> tuple:
        """
        Processes and aligns all input data for modeling.

        Parameters:
        -----------
        prices : pd.DataFrame
            DataFrame containing daily closing prices.
        market_returns : pd.Series
            Series containing market index returns.
        risk_free_rate : pd.Series
            Series containing risk-free rate data.
        market_cap : pd.Series
            Series containing market capitalization data.
        usd_to_rial : pd.Series
            Series containing USD to Rial exchange rates.

        Returns:
        --------
        tuple
            Tuple containing X_train, X_test, y_train, y_test DataFrames/Series.
        """
        try:
            # Calculate returns
            stock_returns = Preprocessor.calculate_returns(prices)

            # Align all datasets
            combined = Preprocessor.align_datasets(
                stock_returns,
                market_returns,
                risk_free_rate,
                market_cap,
                usd_to_rial
            )

            if combined.empty:
                logger.error("Combined dataset is empty after alignment.")
                return None, None, None, None

            # Define feature set (X) and target variables (y)
            X = stock_returns.loc[combined.index]
            y_excess = market_returns.loc[combined.index] - risk_free_rate.loc[combined.index]
            y_market_cap_change = market_cap.loc[combined.index].pct_change().bfill()
            y_usd_to_rial_change = usd_to_rial.loc[combined.index].pct_change().bfill()

            # Create y DataFrame with multiple factors
            y = pd.DataFrame({
                'excess_return': y_excess,
                'market_cap_change': y_market_cap_change,
                'usd_to_rial_change': y_usd_to_rial_change
            }).dropna()

            # Align X and y
            combined_final = X.loc[y.index]
            if combined_final.empty:
                logger.error("No overlapping data between X and y after processing.")
                return None, None, None, None

            # Split Data into Training and Testing Sets (e.g., 67-33 split as per original code)
            X_train, X_test, y_train, y_test = train_test_split(
                combined_final, y, test_size=0.33, shuffle=False
            )
            logger.info(f"Data split into training (size={X_train.shape}) and testing (size={X_test.shape}) sets.")
            return X_train, X_test, y_train, y_test
        except Exception as e:
            logger.error(f"Error during data preprocessing: {e}")
            return None, None, None, None

# %%
# OptimizerModel Class
# ====================
class OptimizerModel:
    """Encapsulates the optimization model creation, fitting, and prediction."""

    def __init__(self, optimizer, name="Optimizer-Model"):
        """
        Initializes the OptimizerModel with the specified optimizer.

        Parameters:
        -----------
        optimizer : skfolio.optimization.BaseRiskParity
            An instance of an optimizer from skfolio.optimization (e.g., HierarchicalRiskParity, DistributionallyRobustCVaR).
        name : str, optional
            Name of the optimizer model (default is "Optimizer-Model").
        """
        self.name = name
        self.optimizer = optimizer

    def fit(self, X_train: pd.DataFrame, y_train: pd.DataFrame = None):
        """
        Fits the optimizer model on the training data.

        Parameters:
        -----------
        X_train : pd.DataFrame
            Training data returns.
        y_train : pd.DataFrame, optional
            Training data factors (default is None).
        """
        try:
            if y_train is not None:
                self.optimizer.fit(X_train, y_train)
            else:
                self.optimizer.fit(X_train)
            logger.info(f"Fitted model '{self.name}'. Weights: {self.optimizer.weights_}")

            # Fit the hierarchical clustering estimator with the correlation matrix
            if hasattr(self.optimizer, 'hierarchical_clustering_estimator') and self.optimizer.hierarchical_clustering_estimator is not None:
                # Compute the correlation matrix
                corr_matrix = X_train.corr()

                # Compute the distance matrix based on the distance estimator
                if isinstance(self.optimizer.distance_estimator, KendallDistance):
                    # Compute Kendall tau correlation
                    kendall_corr = X_train.corr(method='kendall')
                    # Convert correlation to distance
                    distance_matrix = 1 - kendall_corr
                else:
                    # Default to Pearson distance (1 - correlation)
                    distance_matrix = 1 - corr_matrix

                # Fit the hierarchical clustering estimator with the distance matrix
                self.optimizer.hierarchical_clustering_estimator.fit(distance_matrix)
                logger.info(f"Fitted hierarchical clustering estimator for model '{self.name}'.")

        except Exception as e:
            logger.error(f"Error fitting model '{self.name}': {e}")

    def predict(self, X: pd.DataFrame):
        """
        Predicts the portfolio based on the fitted optimizer.

        Parameters:
        -----------
        X : pd.DataFrame
            DataFrame of returns to predict on.

        Returns:
        --------
        Portfolio | Population
            Predicted portfolio or population of portfolios.
        """
        try:
            prediction = self.optimizer.predict(X)
            logger.info(f"Predicted portfolio for model '{self.name}'.")
            return prediction
        except Exception as e:
            logger.error(f"Error predicting portfolio for model '{self.name}': {e}")
            return None

    def plot_dendrogram(self, heatmap=False):
        """
        Plots the dendrogram of the hierarchical clustering if supported by the optimizer.

        Parameters:
        -----------
        heatmap : bool, optional
            Whether to display the heatmap of the reordered distance matrix (default is False).
        """
        try:
            # Corrected attribute name: 'hierarchical_clustering_estimator' without underscore
            if hasattr(self.optimizer, 'hierarchical_clustering_estimator') and \
               hasattr(self.optimizer.hierarchical_clustering_estimator, 'plot_dendrogram'):
                fig = self.optimizer.hierarchical_clustering_estimator.plot_dendrogram(heatmap=heatmap)
                show(fig)
                logger.info(f"Plotted dendrogram for model '{self.name}'.")
            else:
                logger.warning(f"Optimizer '{self.name}' does not support dendrogram plotting.")
        except Exception as e:
            logger.error(f"Error plotting dendrogram for model '{self.name}': {e}")

# %%
# Evaluator Class
# ================
class Evaluator:
    """Handles evaluation of models, including risk contributions, dendrograms, and summary statistics."""

    @staticmethod
    def analyze_risk_contribution(portfolio, measure=RiskMeasure.VARIANCE):
        """
        Analyzes and plots the risk contribution of the portfolio.

        Parameters:
        -----------
        portfolio : Portfolio | Population
            The portfolio or population of portfolios to analyze.
        measure : RiskMeasure, optional
            The risk measure to use for analysis (default is VARIANCE).
        """
        try:
            portfolio.plot_contribution(measure=measure)
            logger.info(f"Plotted risk contribution using {measure}.")
        except Exception as e:
            logger.error(f"Error plotting risk contribution: {e}")

    @staticmethod
    def plot_cumulative_returns(population: Population):
        """
        Plots the cumulative returns of the population of portfolios.

        Parameters:
        -----------
        population : Population
            The population containing multiple portfolios.
        """
        try:
            population.plot_cumulative_returns()
            logger.info("Plotted cumulative returns for the population.")
        except Exception as e:
            logger.error(f"Error plotting cumulative returns: {e}")

    @staticmethod
    def plot_composition(population: Population):
        """
        Plots the composition of the portfolios in the population.

        Parameters:
        -----------
        population : Population
            The population containing multiple portfolios.
        """
        try:
            population.plot_composition()
            logger.info("Plotted composition for the population.")
        except Exception as e:
            logger.error(f"Error plotting composition: {e}")

    @staticmethod
    def print_summary(population: Population):
        """
        Prints the summary statistics of the population.

        Parameters:
        -----------
        population : Population
            The population containing multiple portfolios.

        Returns:
        --------
        pd.DataFrame
            The summary statistics DataFrame.
        """
        try:
            summary = population.summary()
            print("Annualized Sharpe Ratio:")
            print(summary.loc["Annualized Sharpe Ratio"])

            # Full Summary
            print("\nFull Summary Statistics:")
            print(summary)
            logger.info("Printed summary statistics for the population.")
            return summary
        except Exception as e:
            logger.error(f"Error printing summary statistics: {e}")
            return None

# %%
# Main Execution Flow
# ====================
def main():
    # ==============================
    # Data Loading via Tkinter
    # ==============================
    logger.info("Starting data loading via Tkinter file dialogs.")

    # Initialize DataLoader instance
    data_loader = DataLoader()

    # Define required file types
    required_file_types = ['market', 'risk_free_rate', 'market_cap', 'usd_to_rial']

    # Load all required data files
    data_files = data_loader.load_multiple_files(required_file_types)

    # Extract individual DataFrames
    market_df = data_files['market']
    risk_free_df = data_files['risk_free_rate']
    market_cap_df = data_files['market_cap']
    usd_to_rial_df = data_files['usd_to_rial']

    logger.info("Successfully loaded all required data files.")

    # ==============================
    # User Input for Symbol IDs
    # ==============================
    # Prompt user to input symbol IDs as a comma-separated string
    symbol_ids_input = input("Enter symbol IDs separated by commas (e.g., 17914401175772326,66682662312253625,28374437855144739): ")
    # Handle multi-line input if necessary
    symbol_ids_input = symbol_ids_input.replace("\n", "").replace("\r", "")
    portfolio_symbol_ids = [symbol_id.strip() for symbol_id in symbol_ids_input.split(',')]

    logger.info(f"Portfolio Symbol IDs: {portfolio_symbol_ids}")

    # ==============================
    # Data Fetching
    # ==============================
    logger.info("Starting to fetch data for portfolio symbols...")
    symbol_data = asyncio.run(DataFetcher.fetch_all_symbols(portfolio_symbol_ids))

    # Combine all symbol data into a single DataFrame
    prices = pd.DataFrame()
    for symbol_id, df in symbol_data.items():
        if not df.empty:
            df = df[['date', 'close']].rename(columns={'close': symbol_id})
            if prices.empty:
                prices = df
            else:
                prices = prices.merge(df, on='date', how='inner')  # Use 'inner' to keep only overlapping dates
    if prices.empty:
        logger.error("No price data fetched for the provided symbol IDs. Exiting.")
        sys.exit(1)
    prices = prices.set_index('date').sort_index()

    logger.info(f"Successfully fetched and combined price data. Total data points: {len(prices)}")

    # ==============================
    # Extract Market Returns, Market Cap, USD to Rial, and Risk-Free Rate
    # ==============================
    # Assuming market_df has 'daily_return' column
    if 'daily_return' not in market_df.columns:
        logger.error("'daily_return' column not found in market data. Exiting.")
        sys.exit(1)
    market_returns = market_df.set_index('date')['daily_return'].rename("market_returns")

    # Assuming risk_free_df has 'risk_free_rate' column
    if 'risk_free_rate' not in risk_free_df.columns:
        logger.error("'risk_free_rate' column not found in risk-free rate data. Exiting.")
        sys.exit(1)
    risk_free_rate = risk_free_df.set_index('date')['risk_free_rate'].rename("risk_free_rate")

    # Assuming market_cap_df has 'market_cap' column
    if 'market_cap' not in market_cap_df.columns:
        logger.error("'market_cap' column not found in market cap data. Exiting.")
        sys.exit(1)
    market_cap = market_cap_df.set_index('date')['market_cap'].rename("market_cap")

    # Assuming usd_to_rial_df has 'usd_to_rial' column
    if 'usd_to_rial' not in usd_to_rial_df.columns:
        logger.error("'usd_to_rial' column not found in USD to Rial data. Exiting.")
        sys.exit(1)
    usd_to_rial = usd_to_rial_df.set_index('date')['usd_to_rial'].rename("usd_to_rial")

    # ==============================
    # Data Preprocessing
    # ==============================
    preprocessor = Preprocessor()
    X_train, X_test, y_train, y_test = preprocessor.process_data(
        prices, market_returns, risk_free_rate, market_cap, usd_to_rial
    )

    if X_train is None:
        logger.error("Data preprocessing failed. Exiting.")
        sys.exit(1)

    # ==============================
    # Model Implementation
    # ==============================
    # Initialize Evaluator instance
    evaluator = Evaluator()

    # Define the linkage methods you want to use
    linkage_methods = [
        LinkageMethod.SINGLE,
        LinkageMethod.COMPLETE,
        LinkageMethod.AVERAGE,
        LinkageMethod.WARD
    ]

    # Define distance estimators you want to use
    distance_estimators = [
        (None, "Pearson"),  # None implies default distance estimator
        (KendallDistance(absolute=True), "Kendall")
    ]

    # Initialize an empty list to hold all models
    models = []

    # Iterate over each combination of linkage methods and distance estimators
    for linkage in linkage_methods:
        for distance_estimator, distance_name in distance_estimators:
            # Define a name for the model based on the linkage and distance method
            distance_label = distance_name if distance_estimator else "Pearson"
            model_name = f"HRP-CVaR-{linkage.value.capitalize()}-{distance_label}"

            # Initialize HierarchicalClustering with the current linkage method
            hierarchical_clustering = HierarchicalClustering(linkage_method=linkage)

            # Initialize HierarchicalRiskParity optimizer with the clustering estimator and distance estimator
            optimizer = HierarchicalRiskParity(
                risk_measure=RiskMeasure.CVAR,
                distance_estimator=distance_estimator,  # Use the specified distance estimator
                prior_estimator=None,     # Defaults to EmpiricalPrior
                hierarchical_clustering_estimator=hierarchical_clustering,
                portfolio_params=dict(name=model_name)
            )

            # Create an OptimizerModel instance and add it to the models list
            model = OptimizerModel(optimizer=optimizer, name=model_name)
            models.append(model)

    # Additionally, include models with different configurations if needed
    # Example: Model with Kendall distance and Ward linkage (already included above)

    # Model 4: DistributionallyRobustCVaR with FactorModel prior
    optimizer4 = DistributionallyRobustCVaR(
        risk_aversion=1.0,
        cvar_beta=0.95,
        wasserstein_ball_radius=0.02,
        prior_estimator=FactorModel(),
        min_weights=0.0,
        max_weights=1.0,
        budget=1.0,
        portfolio_params=dict(name="DistributionallyRobustCVaR-Factor-Model"),
        solver='CLARABEL',
        solver_params=None,
        scale_objective=None,
        scale_constraints=None,
        save_problem=False,
        raise_on_failure=True
    )
    model4 = OptimizerModel(optimizer=optimizer4, name="DistributionallyRobustCVaR-Factor-Model")
    models.append(model4)

    # ==============================
    # Fit Models
    # ==============================
    for model in models:
        # Only models with "Factor" in their name use y_train
        if "Factor" in model.name:
            model.fit(X_train, y_train)
        else:
            model.fit(X_train)

    # ==============================
    # Benchmarking with Equal Weighted Estimator
    # ==============================
    bench_optimizer = EqualWeighted(portfolio_params=dict(name="EqualWeighted"))
    benchmark = OptimizerModel(optimizer=bench_optimizer, name="EqualWeighted")
    benchmark.fit(X_train)
    models.append(benchmark)

    # ==============================
    # Risk Contribution Analysis and Dendrograms
    # ==============================
    for model in models[:-1]:  # Exclude benchmark
        # Risk Contribution Analysis
        portfolio = model.predict(X_train)
        if portfolio is not None:
            evaluator.analyze_risk_contribution(portfolio, measure=RiskMeasure.CVAR)
        # Dendrogram (if applicable)
        model.plot_dendrogram(heatmap=True)

    # ==============================
    # Prediction on Test Set
    # ==============================
    population_test = Population([])
    for model in models:
        portfolio = model.predict(X_test)
        if portfolio is not None:
            population_test.append(portfolio)
            logger.info(f"Appended portfolio from model '{model.name}' to population.")
        else:
            logger.warning(f"Skipped appending portfolio from model '{model.name}' due to prediction failure.")

        # ==============================
        # Evaluation
        # ==============================
        # Plot Cumulative Returns
        evaluator.plot_cumulative_returns(population_test)

        # Plot Portfolio Composition
        evaluator.plot_composition(population_test)

        # Print Summary Statistics and Retrieve Summary DataFrame
        summary = evaluator.print_summary(population_test)

        if summary is None:
            logger.error("Summary statistics could not be printed.")
            sys.exit(1)

    # ==============================
    # Export Optimized Portfolios and Rank Them
    # ==============================
    try:
        # Initialize an empty dictionary to store weights
        portfolio_weights = {}

        # Iterate over each model and extract weights
        for model in models:
            # Predict portfolio on the training set to get the weights
            portfolio = model.predict(X_train)  # Alternatively, use X_test or any specific date
            if portfolio is not None:
                # Ensure weights are a Series with symbol IDs as index
                weights = pd.Series(portfolio.weights, index=X_train.columns)
                portfolio_weights[model.name] = weights
                logger.info(f"Extracted weights for model '{model.name}'.")
            else:
                logger.warning(f"Cannot extract weights for model '{model.name}' as prediction failed.")

        # Create a DataFrame from the weights dictionary
        weights_df = pd.DataFrame(portfolio_weights).transpose()

        # Reset index to have model names as a column
        weights_df = weights_df.reset_index().rename(columns={'index': 'Model'})

        # Display the weights DataFrame
        print("\nOptimized Portfolio Weights:")
        print(weights_df)

        # ==============================
        # Ranking Portfolios Based on Annualized Sharpe Ratio
        # ==============================
        # Extract Annualized Sharpe Ratio and rank the models
        sharpe_ratios = summary.loc["Annualized Sharpe Ratio"]

        # Create a DataFrame for rankings
        ranking_df = sharpe_ratios.reset_index().rename(columns={'index': 'Model', 'Annualized Sharpe Ratio': 'Sharpe Ratio'})
        ranking_df['Rank'] = ranking_df['Sharpe Ratio'].rank(ascending=False, method='dense').astype(int)
        ranking_df = ranking_df.sort_values('Rank')

        # Merge ranking into weights_df
        weights_df = weights_df.merge(ranking_df[['Model', 'Sharpe Ratio', 'Rank']], on='Model', how='left')

        # Reorder columns to have 'Rank' first
        cols = ['Rank', 'Model'] + [col for col in weights_df.columns if col not in ['Rank', 'Model']]
        weights_df = weights_df[cols]

        # Display the ranking
        print("\nPortfolio Rankings based on Annualized Sharpe Ratio:")
        print(ranking_df.sort_values('Rank'))

        # Export to CSV
        weights_df.to_csv('Optimized_Portfolio_Weights.csv', index=False, encoding='utf-8-sig')
        logger.info("Exported optimized portfolio weights to 'Optimized_Portfolio_Weights.csv'.")

        # Export to Excel (Specify engine)
        weights_df.to_excel('Optimized_Portfolio_Weights.xlsx', index=False, engine='openpyxl')
        logger.info("Exported optimized portfolio weights to 'Optimized_Portfolio_Weights.xlsx'.")

    except Exception as e:
        logger.error(f"Error exporting portfolio weights: {e}")


# %%
# Execute Main Function
# ======================
if __name__ == "__main__":
    main()
