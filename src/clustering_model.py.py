import pandas as pd
import numpy as np
import math

# -----------------------------------------------------------------
# --- 1. CONFIGURATION ---
# -----------------------------------------------------------------
# UPDATE THESE PATHS MANUALLY
input_file = r"../data/weekly_user_kpi.csv"
output_users = r"../data/segmented_users.csv"
output_summary = r"../data/cluster_summary.csv"

# -----------------------------------------------------------------
# --- 2. LOAD AND PREPARE DATA ---
# -----------------------------------------------------------------
print(f"Loading data from: {input_file}")
data = pd.read_csv(input_file)

# --- Convert columns to numeric ---
if data["THEO_WIN"].dtype == 'object':
    data["THEO_WIN"] = data["THEO_WIN"].replace({",": ""}, regex=True).astype(float)
else:
    data["THEO_WIN"] = data["THEO_WIN"].astype(float)

data["DAYS_PLAYED"] = pd.to_numeric(data["DAYS_PLAYED"], errors="coerce")

# --- Fill missing values ---
data["THEO_WIN"].fillna(0, inplace=True)
data["DAYS_PLAYED"].fillna(0, inplace=True)

# --- Calculate Weekly ADT ---
data["ADT"] = data["THEO_WIN"] / data["DAYS_PLAYED"]
data["ADT"].fillna(0, inplace=True)
data["ADT"].replace([np.inf, -np.inf], 0, inplace=True)

# -----------------------------------------------------------------
# --- 3. AGGREGATE BY USER ---
# -----------------------------------------------------------------
print("Aggregating data...")
user_averages = data.groupby('GGPASS_ID')[['THEO_WIN', 'DAYS_PLAYED', 'ADT']].mean()
user_averages = user_averages.rename(columns={
    "THEO_WIN": "AVG_WEEKLY_THEO_WIN",
    "DAYS_PLAYED": "AVG_WEEKLY_DAYS_PLAYED",
    "ADT": "AVG_WEEKLY_ADT"
})

# --- FILTER: REMOVE USERS WITH AVG THEO < 10 ---
user_averages = user_averages[user_averages["AVG_WEEKLY_THEO_WIN"] >= 10].copy()
print(f"*** Users Remaining (Theo >= 10): {len(user_averages)} ***")

# Get Overall Totals & Metadata
user_totals = data.groupby('GGPASS_ID')[['THEO_WIN', 'DAYS_PLAYED']].sum()
user_totals['OVERALL_ADT'] = user_totals['THEO_WIN'] / user_totals['DAYS_PLAYED']
user_totals['OVERALL_ADT'].fillna(0, inplace=True)
user_totals['OVERALL_ADT'].replace([np.inf, -np.inf], 0, inplace=True)
user_totals = user_totals.rename(columns={"THEO_WIN": "OVERALL_THEO_WIN", "DAYS_PLAYED": "OVERALL_DAYS_PLAYED"})

user_info = data.groupby('GGPASS_ID')[['BRAND_ID', 'SITE_ID', 'NICKNAME', 'CID', 'TOP_CATEGORY']].first()

# -----------------------------------------------------------------
# --- 4. PREPARE FOR CLUSTERING ---
# -----------------------------------------------------------------
cluster_features = user_averages[["AVG_WEEKLY_THEO_WIN", "AVG_WEEKLY_DAYS_PLAYED"]].copy()
cluster_features["LOG_THEO"] = np.log10(cluster_features["AVG_WEEKLY_THEO_WIN"] + 1)

X = cluster_features[["LOG_THEO", "AVG_WEEKLY_DAYS_PLAYED"]].to_numpy()

# -----------------------------------------------------------------
# --- 5. CLUSTERING FUNCTIONS ---
# -----------------------------------------------------------------

def kmedians(X, n_clusters, max_iter=100, random_state=100):
    np.random.seed(random_state)
    if len(X) < n_clusters:
        return np.zeros(len(X)), np.zeros((0, X.shape[1])), 0

    medoid_ids = np.random.choice(len(X), n_clusters, replace=False)
    medoids = X[medoid_ids]
    labels = np.zeros(len(X))
    total_cost = 0

    for _ in range(max_iter):
        distances = np.abs(X[:, None, :] - medoids[None, :, :]).sum(axis=2)
        labels = np.argmin(distances, axis=1)
        min_distances = np.min(distances, axis=1)
        total_cost = np.sum(min_distances)

        new_medoids = np.array([
            np.median(X[labels == k], axis=0) if np.any(labels == k) else medoids[k]
            for k in range(n_clusters)
        ])
        if np.allclose(new_medoids, medoids):
            break
        medoids = new_medoids
        
    return labels, medoids, total_cost

def find_optimal_k(X, max_k=15):
    print(f"Calculating Optimal K (testing 1 to {max_k} clusters)...")
    costs = []
    k_range = list(range(1, max_k + 1))
    for k in k_range:
        _, _, cost = kmedians(X, n_clusters=k)
        costs.append(cost)

    p1 = np.array([k_range[0], costs[0]])
    p2 = np.array([k_range[-1], costs[-1]])
    max_distance = 0
    best_k = k_range[0]

    for k, cost in zip(k_range, costs):
        p0 = np.array([k, cost])
        numerator = np.abs((p2[1] - p1[1])*p0[0] - (p2[0] - p1[0])*p0[1] + p2[0]*p1[1] - p2[1]*p1[0])
        denominator = np.sqrt((p2[1] - p1[1])**2 + (p2[0] - p1[0])**2)
        distance = numerator / denominator
        if distance > max_distance:
            max_distance = distance
            best_k = k
            
    print(f" -> Elbow found at k={best_k}")
    return best_k

# -----------------------------------------------------------------
# --- 6. EXECUTION ---
# -----------------------------------------------------------------

# A. Find Optimal Number of Clusters
optimal_k = find_optimal_k(X, max_k=15)

# B. Run Final Clustering
print(f"Running Final Clustering with {optimal_k} clusters...")
labels, medoids, _ = kmedians(X, n_clusters=optimal_k)
user_averages["CLUSTER"] = labels

# C. Sort Clusters by Value
temp_summary = user_averages.groupby("CLUSTER")["AVG_WEEKLY_THEO_WIN"].mean().reset_index()
temp_summary = temp_summary.sort_values(by="AVG_WEEKLY_THEO_WIN", ascending=True).reset_index(drop=True)
temp_summary["new_CLUSTER_id"] = temp_summary.index + 1 
cluster_mapping = dict(zip(temp_summary["CLUSTER"], temp_summary["new_CLUSTER_id"]))
user_averages["CLUSTER"] = user_averages["CLUSTER"].map(cluster_mapping)

# D. Calculate CB_AMOUNT
print("Calculating CB_AMOUNT based on Cluster Averages...")
cluster_means = user_averages.groupby("CLUSTER")["AVG_WEEKLY_THEO_WIN"].mean()

def calculate_cb_amount(mean_val):
    val_10_percent = mean_val * 0.10
    return math.ceil(val_10_percent / 10.0) * 10

cluster_cb_map = cluster_means.apply(calculate_cb_amount).to_dict()
print("Offer Amounts per Cluster:", cluster_cb_map)
user_averages["CB_AMOUNT"] = user_averages["CLUSTER"].map(cluster_cb_map)

# -----------------------------------------------------------------
# --- 7. SAVE FINAL FILES ---
# -----------------------------------------------------------------

# Summary (FIXED: Count 'AVG_WEEKLY_THEO_WIN' instead of 'CLUSTER')
final_summary = user_averages.groupby("CLUSTER")[["AVG_WEEKLY_THEO_WIN", "AVG_WEEKLY_DAYS_PLAYED", "CB_AMOUNT"]].agg(
    {"AVG_WEEKLY_THEO_WIN": ["mean", "median", "min", "max", "count"],  # <--- Added 'count' here
     "AVG_WEEKLY_DAYS_PLAYED": ["mean", "median"],
     "CB_AMOUNT": "first"}
)

# Rename Columns
final_summary.columns = ['_'.join(col).strip() for col in final_summary.columns.values]
final_summary = final_summary.rename(columns={
    "AVG_WEEKLY_THEO_WIN_count": "USER_COUNT",  # Rename to USER_COUNT
    "CB_AMOUNT_first": "CB_AMOUNT"
})
final_summary = final_summary.reset_index()

# User Data
final_user_data = user_averages[['CLUSTER', 'CB_AMOUNT', 'AVG_WEEKLY_THEO_WIN', 'AVG_WEEKLY_DAYS_PLAYED', 'AVG_WEEKLY_ADT']].join(user_info)
final_user_data = final_user_data.join(user_totals[['OVERALL_THEO_WIN', 'OVERALL_ADT', 'OVERALL_DAYS_PLAYED']])
final_user_data = final_user_data.reset_index()

# Save
final_user_data.to_csv(output_users, index=False)
final_summary.to_csv(output_summary, index=False)

print("-" * 30)
print(f"PROCESS COMPLETE. Used {optimal_k} clusters.")
print(f"Files saved to:\n{output_users}\n{output_summary}")