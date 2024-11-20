# HRP
Hierarchical Risk Parity




---

## **مقدمه**

در این پروژه، هدف اصلی ما بهینه‌سازی پرتفو سرمایه‌گذاری با استفاده از روش‌های پیشرفته **Hierarchical Risk Parity (HRP)** و **Conditional Value at Risk (CVaR)** است. این فرآیند شامل مراحل مختلفی از انتخاب نمادها، بارگذاری و پردازش داده‌ها، بهینه‌سازی پرتفو، تا ارزیابی و ذخیره نتایج می‌باشد. در ادامه، به تفصیل هر یک از این مراحل و اجزای کد را شرح می‌دهیم.

---

## **۱. انتخاب جفت‌ها (Combination Selection)**

### **تولید ترکیب‌های پرتفو:**

اولین قدم در این فرآیند، تولید تمامی ترکیب‌های ممکن از نمادهای انتخاب شده است. فرض کنید ما مجموعه‌ای از نمادهای سهامی داریم و می‌خواهیم تمامی ترکیب‌های ممکن از ۱۰ نماد را بررسی کنیم تا بهترین پرتفو را شناسایی کنیم. برای این منظور از کتابخانه `itertools` و تابع `combinations` استفاده کرده‌ایم.

```python
def generate_combinations(symbol_ids: list, portfolio_size: int = 10) -> list:
    return list(itertools.combinations(symbol_ids, portfolio_size))
```

این تابع، تمامی ترکیب‌های ممکن از ۱۰ نماد را ایجاد کرده و به عنوان ورودی برای تحلیل‌های بعدی آماده می‌کند.

### **نمونه‌گیری از ترکیب‌ها:**

با توجه به تعداد بسیار زیاد ترکیب‌های ممکن، پردازش تمامی آنها ممکن است زمان‌بر و منابع‌بر باشد. بنابراین، تصمیم گرفتیم تعداد ترکیب‌های مورد بررسی را به یک مقدار مشخص محدود کنیم. برای این منظور از تابع `random.sample` استفاده می‌کنیم تا به طور تصادفی تعدادی ترکیب را انتخاب کنیم.

```python
desired_samples = 100000  # تعداد نمونه‌های مورد نظر
if total_combinations > desired_samples:
    sampled_combinations = random.sample(portfolio_combinations, desired_samples)
else:
    sampled_combinations = portfolio_combinations
```

این بخش از کد تضمین می‌کند که تنها تعداد معینی از ترکیب‌ها برای تحلیل انتخاب شوند، که این امر به کاهش بار محاسباتی و افزایش کارایی کمک می‌کند.

---

## **۲. بارگذاری و پردازش داده‌ها**

### **کلاس DataFetcher:**

این کلاس مسئولیت بارگذاری و پردازش داده‌های روزانه نمادها را بر عهده دارد. با استفاده از API مربوطه، داده‌های تاریخی قیمت نمادها را دریافت کرده و آنها را به فرمت مناسب تبدیل می‌کند.

```python
class DataFetcher:
    """Class responsible for fetching and processing data from the API."""
    ...
```

#### **متد fetch_daily_history:**

این متد به صورت غیرهمزمان داده‌های تاریخی روزانه یک نماد را دریافت می‌کند. در این فرآیند، تاریخ‌های جلالی به میلادی تبدیل می‌شوند و داده‌های خالی یا نامعتبر حذف می‌شوند.

```python
@staticmethod
async def fetch_daily_history(symbol_id: str) -> pd.DataFrame:
    ...
```

#### **متد fetch_all_symbols:**

این متد برای تمامی نمادهای ورودی، به صورت همزمان داده‌ها را دریافت می‌کند و آنها را در یک دیکشنری نگهداری می‌کند.

```python
@staticmethod
async def fetch_all_symbols(symbol_ids: list) -> dict:
    ...
```

### **کلاس DataLoader:**

این کلاس مسئول بارگذاری داده‌های خارجی مانند شاخص بازار، بازار سرمایه، نرخ تبدیل ارز و نرخ بدون ریسک از فایل‌های انتخابی کاربر است. با استفاده از کتابخانه `tkinter`، فایل‌ها توسط کاربر انتخاب می‌شوند و سپس با استفاده از تطبیق فازی (`fuzzywuzzy`) ستون‌های مورد نیاز شناسایی می‌شوند.

```python
class DataLoader:
    """Class responsible for loading and processing external data files."""
    ...
```

#### **متد load_data:**

این متد فایل‌های اکسل یا CSV را بارگذاری کرده و ستون‌های مورد نیاز را با استفاده از تطبیق فازی شناسایی و استاندارد می‌کند.

```python
@staticmethod
def load_data(file_type: str) -> pd.DataFrame:
    ...
```

#### **متد load_multiple_files:**

این متد برای بارگذاری چندین نوع فایل به صورت همزمان استفاده می‌شود.

```python
@staticmethod
def load_multiple_files(file_types: list) -> dict:
    ...
```

### **کلاس Preprocessor:**

این کلاس مسئولیت پیش‌پردازش داده‌ها، محاسبه بازده‌ها و هم‌ترازی داده‌ها را بر عهده دارد.

```python
class Preprocessor:
    """Handles data preprocessing steps such as calculating returns and aligning datasets."""
    ...
```

#### **متد calculate_returns:**

این متد بازده‌های روزانه را از داده‌های قیمت محاسبه می‌کند.

```python
@staticmethod
def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    ...
```

#### **متد align_datasets:**

این متد داده‌های مختلف را بر اساس تاریخ مشترک هم‌تراز می‌کند تا تحلیل‌های بعدی دقیق‌تر انجام شود.

```python
@staticmethod
def align_datasets(*datasets: pd.DataFrame) -> pd.DataFrame:
    ...
```

#### **متد process_data:**

این متد تمامی داده‌های ورودی را پردازش کرده و داده‌های آموزشی و تست را به صورت `X_train`, `X_test`, `y_train`, و `y_test` آماده می‌کند.

```python
@staticmethod
def process_data(prices: pd.DataFrame, market_returns: pd.Series, risk_free_rate: pd.Series,
                market_cap: pd.Series, usd_to_rial: pd.Series) -> tuple:
    ...
```

در اینجا، `X_train` و `X_test` شامل بازده‌های روزانه نمادها هستند، در حالی که `y_train` و `y_test` شامل بازده‌های اضافه، تغییرات بازار سرمایه و تغییرات نرخ تبدیل ارز می‌باشند.

---

## **۳. پیاده‌سازی مدل‌های بهینه‌سازی**

### **کلاس OptimizerModel:**

این کلاس نقش مرکزی در بهینه‌سازی پرتفو دارد. هر نمونه از این کلاس یک مدل بهینه‌سازی خاص را با استفاده از یکی از روش‌های HRP یا CVaR پیاده‌سازی می‌کند.

```python
class OptimizerModel:
    """Encapsulates the optimization model creation, fitting, and prediction."""
    ...
```

#### **متد __init__:**

در این متد، مدل بهینه‌سازی با استفاده از شیء `optimizer` که از کتابخانه `skfolio` استخراج شده، مقداردهی اولیه می‌شود.

```python
def __init__(self, optimizer, name="Optimizer-Model"):
    ...
```

#### **متد fit:**

این متد مدل را روی داده‌های آموزشی برازش می‌دهد. اگر مدل از نوع HRP باشد، ماتریس همبستگی محاسبه شده و بر اساس آن، خوشه‌بندی سلسله‌مراتبی انجام می‌شود.

```python
def fit(self, X_train: pd.DataFrame, y_train: pd.DataFrame = None):
    ...
```

#### **متد predict:**

این متد وزن‌های پرتفو را بر اساس مدل برازش شده پیش‌بینی می‌کند.

```python
def predict(self, X: pd.DataFrame):
    ...
```

#### **متد plot_dendrogram:**

اگر مدل از نوع HRP باشد، این متد نمودار درختی خوشه‌بندی سلسله‌مراتبی را نمایش می‌دهد.

```python
def plot_dendrogram(self, heatmap=False):
    ...
```

### **تعریف مدل‌ها:**

در بخش اصلی کد (`main`)، مدل‌های مختلف با استفاده از ترکیب‌های مختلف روش‌های لینکج و تخمین‌گرهای فاصله تعریف می‌شوند. علاوه بر این، مدل Distributionally Robust CVaR با استفاده از مدل عامل (Factor Model) نیز اضافه می‌شود.

```python
for linkage in linkage_methods:
    for distance_estimator, distance_name in distance_estimators:
        ...
        model = OptimizerModel(optimizer=optimizer, name=model_name)
        models.append(model)

# اضافه کردن مدل DistributionallyRobustCVaR با FactorModel
optimizer4 = DistributionallyRobustCVaR(...)
model4 = OptimizerModel(optimizer=optimizer4, name="DistributionallyRobustCVaR-Factor-Model")
models.append(model4)
```

---

## **۴. تخصیص ریسک و وزن‌دهی به پرتفو**

### **تخصیص ریسک:**

هدف از تخصیص ریسک، تعیین سهم هر نماد در کل ریسک پرتفو است. با استفاده از معیارهای مختلف ریسک مانند واریانس و CVaR، سهم هر نماد از ریسک محاسبه می‌شود. سپس با استفاده از نمودارهای مشارکت ریسک، تخصیص ریسک به صورت بصری نمایش داده می‌شود.

```python
portfolio.plot_contribution(measure=RiskMeasure.CVAR)
```

### **وزن‌دهی به پرتفو:**

پس از تخصیص ریسک، وزن‌های بهینه برای هر نماد در پرتفو محاسبه می‌شود. این وزن‌ها نشان‌دهنده میزان سرمایه‌گذاری در هر نماد هستند و باید مجموع آنها برابر با ۱ و در محدوده مجاز باشند.

```python
portfolio_weights[model.name] = weights.to_dict()
```

---

## **۵. ارزیابی مدل‌ها و محاسبه متریک‌های پرتفو**

### **کلاس Evaluator:**

این کلاس مسئولیت ارزیابی مدل‌ها و محاسبه متریک‌های عملکرد پرتفو را بر عهده دارد.

```python
class Evaluator:
    """Handles evaluation of models, including risk contributions, dendrograms, summary statistics, and performance metrics."""
    ...
```

#### **متد calculate_performance_metrics:**

این متد متریک‌های مختلفی از جمله Sharpe Ratio، Sortino Ratio، VaR، CVaR، و واریانس را برای بازده‌های پرتفو محاسبه می‌کند.

```python
@staticmethod
def calculate_performance_metrics(portfolio_returns: pd.Series, risk_free_rate: float = 0.0) -> dict:
    ...
```

#### **متد print_summary:**

این متد خلاصه‌ای از متریک‌های محاسبه شده را چاپ می‌کند.

```python
@staticmethod
def print_summary(population: Population):
    ...
```

### **محاسبه متریک‌های عملکرد:**

برای هر پرتفو، بازده‌های روزانه بر اساس وزن‌های تعیین شده محاسبه می‌شود و سپس متریک‌های عملکرد بر اساس این بازده‌ها محاسبه می‌گردد.

```python
portfolio_returns = X_test.dot(weights)
metrics = Evaluator.calculate_performance_metrics(portfolio_returns, risk_free_rate=avg_risk_free_rate)
```

### **خلاصه‌سازی نتایج:**

نتایج به دست آمده شامل ترکیب پرتفو، وزن‌های مدل‌ها و متریک‌های عملکرد به صورت یک DataFrame جامع ذخیره می‌شوند و سپس در فایل‌های CSV و Excel صادر می‌شوند.

```python
results_df.to_csv('Optimized_Portfolio_Weights_Combinations.csv', index=False, encoding='utf-8-sig')
results_df.to_excel('Optimized_Portfolio_Weights_Combinations.xlsx', index=False, engine='openpyxl')
```

---

## **۶. مدیریت و بهینه‌سازی فرآیند**

### **پردازش موازی و غیرهمزمان:**

با توجه به تعداد زیاد ترکیب‌ها، استفاده از پردازش موازی و غیرهمزمان برای افزایش کارایی و کاهش زمان پردازش ضروری است. در این پروژه از کتابخانه‌های `asyncio` و `concurrent.futures` استفاده شده است تا پردازش‌های مربوط به ترکیب‌های پرتفو به صورت همزمان انجام شوند.

```python
for combination in tqdm(sampled_combinations, desc="Processing Portfolio Combinations"):
    result = asyncio.run(process_portfolio_combination(combination, data_files, preprocessor, models))
    if result:
        results.append(result)
```

### **مدیریت خطا و ثبت لاگ‌ها:**

برای اطمینان از اجرای پایدار کد و پیگیری خطاها، از کتابخانه `logging` استفاده شده است. تمامی مراحل با ثبت لاگ‌های مناسب قابل پیگیری هستند و در صورت بروز خطا، اطلاعات دقیق آن ثبت می‌شود.

```python
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
```

---

## **۷. اجرای جریان اصلی (Main Execution Flow)**

در بخش اصلی کد (`main`)، تمامی مراحل بالا به ترتیب و به صورت همزمان اجرا می‌شوند:

1. **بارگذاری داده‌ها:** با استفاده از کلاس‌های `DataLoader` و `DataFetcher`، داده‌های مورد نیاز بارگذاری و پردازش می‌شوند.
2. **تعریف مدل‌ها:** مدل‌های بهینه‌سازی با استفاده از کلاس `OptimizerModel` تعریف و مقداردهی اولیه می‌شوند.
3. **تولید ترکیب‌های پرتفو:** تمامی ترکیب‌های ممکن از نمادها تولید و در صورت لزوم نمونه‌گیری می‌شوند.
4. **پردازش ترکیب‌ها:** برای هر ترکیب پرتفو، داده‌ها آماده شده و مدل‌ها برازش و وزن‌های پرتفو پیش‌بینی می‌شوند.
5. **محاسبه متریک‌ها:** متریک‌های عملکرد پرتفو محاسبه و نتایج ذخیره می‌شوند.
6. **خلاصه‌سازی و صادرات نتایج:** نتایج به صورت فایل‌های CSV و Excel صادر شده و پرتفوهای برتر نمایش داده می‌شوند.

---

## **نتیجه‌گیری**

با استفاده از این کد، شما یک ابزار قدرتمند و جامع برای بهینه‌سازی پرتفو در اختیار دارید که از روش‌های پیشرفته‌ای مانند **Hierarchical Risk Parity (HRP)** و **Conditional Value at Risk (CVaR)** بهره می‌برد. این ابزار قادر است تا با تحلیل دقیق داده‌ها، وزن‌های بهینه را تعیین کرده و پرتفوهایی با ریسک پایین و بازدهی مطلوب ایجاد کند.

استفاده از پردازش‌های موازی و مدیریت دقیق خطاها نشان از توجه ویژه شما به کارایی و پایداری کد دارد. همچنین، محاسبه متریک‌های متعدد مانند Sharpe Ratio، Sortino Ratio، VaR و CVaR، امکان ارزیابی جامع پرتفوها را فراهم می‌کند.

