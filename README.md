# Behavioral Segmentation & CRM Optimization using K-Medians Clustering

## 1. Executive Summary
> **Designed and executed a targeted CRM campaign strategy for active JDB(game provider name) players. By replacing static offer rules with a machine learning approach (K-Medians Clustering), I identified four distinct player personas. The resulting model projected a 576% ROI and a $19K lift in Theoretical Win, optimizing marketing spend by dynamically aligning offer amounts to player value.**
---

## 2. The Problem (Situation)

- **Context:** The CRM team needed to engage active users without overspending on “spray and pray” bonuses.
- **Challenge:** Historical data showed that a one-size-fits-all offer was inefficient—either too low to incentivize high rollers or too high for casual players, wasting budget.
- **Goal:** Create a data-driven segmentation strategy to assign the *right* offer amount to the *right* user.

---

## 3. The Solution (Methodology)

### Step 1: Feature Engineering (SQL)
Aggregated raw gameplay logs in Snowflake to create user-level features:
- `AVG_WEEKLY_THEO_WIN`
- `AVG_WEEKLY_DAYS_PLAYED`

---

### Step 2: Unsupervised Learning (Python)

- Applied **log transformation** to `THEO_WIN` to handle highly skewed data distributions (long tail of high rollers).
- Utilized **K-Medians Clustering** (chosen over K-Means for robustness against outliers) to uncover natural groupings in player behavior.
- Determined **optimal K = 4** using the **Elbow Method**.

---

### Step 3: Offer Optimization

- Calculated dynamic `CB_AMOUNT` (Cash Bonus) for each cluster:
  - **10% of the cluster’s average Theo Win**
  - Rounded **up** for clean marketing execution

**Example**
- Cluster 1 (Casuals): **$10**
- Cluster 4 (VIPs): **$80**

---

### Step 4: ROI Modeling (Snowflake)
Uploaded the segmented player list back into Snowflake and ran a predictive lift analysis using historical conversion assumptions:
- **30% Redemption Rate**
- **55% Cash Conversion Factor**

---

## 4. Key Technical Highlights

### Snippet 1: Handling Skewed Data & Feature Preparation (Python)
Gambling data is heavily right-skewed, with a small number of high-value “whales.” To ensure accurate clustering, a log transformation was applied prior to modeling.

```python
# Feature Scaling: Log Transformation to normalize skewed data
cluster_features["LOG_THEO"] = np.log10(
    cluster_features["AVG_WEEKLY_THEO_WIN"] + 1
)

# Prepare feature matrix for clustering
X = cluster_features[
    ["LOG_THEO", "AVG_WEEKLY_DAYS_PLAYED"]
].to_numpy()
```

---

### Snippet 2: K-Medians Clustering Execution (Python)
K-Medians minimizes Manhattan distance instead of Euclidean distance, making the model resilient to extreme outliers (e.g., a single $50K win).

```python
# Determine optimal number of clusters using the Elbow Method
optimal_k = find_optimal_k(X, max_k=15)
print(f"Elbow found at k={optimal_k}")

# Run final K-Medians clustering
labels, medoids, _ = kmedians(X, n_clusters=optimal_k)

# Assign cluster labels back to the dataset
user_averages["CLUSTER"] = labels
```

---

### Snippet 3: Automating Offer Assignment Logic (Python)
Manual Excel-based bonus assignment was replaced with a repeatable and auditable Python function.

```python
def calculate_cb_amount(mean_val):
    """
    Strategy:
    - 10% of cluster mean Theo Win
    - Rounded UP to the nearest $10
    """
    val_10_percent = mean_val * 0.10
    return math.ceil(val_10_percent / 10.0) * 10

# Map cluster IDs to Cash Bonus amounts
cluster_means = (
    user_averages
    .groupby("CLUSTER")["AVG_WEEKLY_THEO_WIN"]
    .mean()
)

cluster_cb_map = cluster_means.apply(calculate_cb_amount).to_dict()
user_averages["CB_AMOUNT"] = user_averages["CLUSTER"].map(cluster_cb_map)
```

---

### Snippet 4: ROI & Lift Modeling (SQL | Snowflake)
A predictive financial model was built to estimate campaign performance, factoring in redemption behavior and cash conversion.

```sql
SELECT 
    'Active Players (JDB_ACTIVE)' AS COHORT_TYPE,

    -- Redeemed Offer Cost
    ROUND(
        (COUNT(DISTINCT GGPASS_ID) * 0.30)
        * AVG(CB_AMOUNT)
        * 0.55
    , 0) AS REDEEMED_OFFER_AMOUNT_COST,

    -- Net Lift in Theoretical Win
    ROUND(
        (((COUNT(DISTINCT GGPASS_ID) * 0.30) * 1)
         * (SUM(AVG_WEEKLY_THEO_WIN)
            / NULLIF(SUM(AVG_WEEKLY_DAYS_PLAYED), 0)))
        -
        ((COUNT(DISTINCT GGPASS_ID) * 0.30)
         * AVG(CB_AMOUNT)
         * 0.55)
    , 0) AS LIFT_NET_THEO,

    -- ROI Calculation
    ROUND(
        LIFT_NET_THEO
        / NULLIF(REDEEMED_OFFER_AMOUNT_COST, 0)
    , 2) AS ROI_PCT

FROM DW_CP.PUBLIC.JDB_ACTIVE_USERS;
```

---

## 5. Results (Business Impact)

- **Targeted Audience:** 751 active players  
- **Projected Lift:** +1 incremental day of play per responder  

### Financial Impact
- **Redeemed Offer Cost:** ~$2.9K  
- **Gross Lift:** ~$19.8K  
- **Net Lift:** ~$16.8K  
- **ROI:** **576%**

---

## 6. Tools & Technologies
- SQL (Snowflake)
- Python (Pandas, NumPy)
- Unsupervised Machine Learning (K-Medians)
- CRM & Marketing Analytics

---

<br>
<small>
<b>🔒 Data Privacy Note:</b> The datasets provided in this repository (`data/`) have been anonymized to protect player privacy. All `GGPASS_ID`, `NICKNAME`, and `CID` values were replaced with synthetic UUIDs or generic labels prior to upload. The behavioral patterns and logic remain authentic to the analysis.
</small>
