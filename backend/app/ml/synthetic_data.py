import numpy as np
import pandas as pd
from typing import List, Dict

# Defines the idealized statistical signature of 19 different crops
# (NDVI_max, NDVI_mean, NDVI_std, Peak_Month, EVI_max, NDWI_max, SAVI_max, GNDVI_max)
CROP_PROFILES = {
    "Wheat (Winter)":           {"base": [0.85, 0.45, 0.25, 3,  0.70, 0.20, 0.50, 0.65], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.10, 0.05, 0.05]},
    "Clover / Berseem":         {"base": [0.75, 0.50, 0.15, 2,  0.65, 0.30, 0.45, 0.60], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.10, 0.05, 0.05]},
    "Barley":                   {"base": [0.80, 0.40, 0.25, 3,  0.65, 0.15, 0.45, 0.60], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.10, 0.05, 0.05]},
    "Winter Onion":             {"base": [0.55, 0.30, 0.15, 4,  0.45, 0.10, 0.35, 0.40], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Garlic":                   {"base": [0.60, 0.35, 0.15, 4,  0.50, 0.10, 0.40, 0.45], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Fava Bean":                {"base": [0.70, 0.45, 0.20, 3,  0.60, 0.25, 0.45, 0.55], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Sugar Beet":               {"base": [0.82, 0.50, 0.20, 5,  0.75, 0.35, 0.55, 0.65], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    
    "Corn / Maize (Summer)":    {"base": [0.88, 0.48, 0.30, 8,  0.80, 0.40, 0.60, 0.70], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.10, 0.05, 0.05]},
    "Cotton":                   {"base": [0.75, 0.42, 0.20, 9,  0.65, 0.25, 0.50, 0.60], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Rice":                     {"base": [0.85, 0.55, 0.25, 8,  0.75, 0.65, 0.55, 0.65], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.15, 0.05, 0.05]},
    "Tomato (Summer)":          {"base": [0.65, 0.38, 0.15, 7,  0.55, 0.30, 0.45, 0.50], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Potato":                   {"base": [0.70, 0.40, 0.20, 6,  0.60, 0.25, 0.45, 0.55], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Sunflower":                {"base": [0.78, 0.45, 0.25, 7,  0.70, 0.20, 0.50, 0.60], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Soybean":                  {"base": [0.80, 0.48, 0.25, 8,  0.75, 0.30, 0.55, 0.65], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},

    "Citrus Orchard":           {"base": [0.65, 0.55, 0.05, 1,  0.50, 0.35, 0.40, 0.55], "spread": [0.05, 0.05, 0.02, 3, 0.05, 0.05, 0.05, 0.05]},
    "Mango Orchard":            {"base": [0.70, 0.60, 0.05, 8,  0.55, 0.40, 0.45, 0.60], "spread": [0.05, 0.05, 0.02, 2, 0.05, 0.05, 0.05, 0.05]},
    "Grapes / Vineyard":        {"base": [0.60, 0.35, 0.20, 6,  0.50, 0.20, 0.40, 0.45], "spread": [0.05, 0.05, 0.05, 1, 0.05, 0.05, 0.05, 0.05]},
    "Alfalfa (Perennial)":      {"base": [0.85, 0.65, 0.10, 5,  0.75, 0.45, 0.60, 0.70], "spread": [0.05, 0.05, 0.05, 3, 0.05, 0.10, 0.05, 0.05]},
    "Fallow / Bare Soil":       {"base": [0.15, 0.10, 0.05, 6,  0.10, -0.1, 0.10, 0.10], "spread": [0.05, 0.05, 0.02, 5, 0.05, 0.05, 0.05, 0.05]}
}

def generate_synthetic_dataset(samples_per_crop=1000) -> pd.DataFrame:
    """Generates a synthetic DataFrame with simulated vegetation index features."""
    data = []
    labels = []
    
    np.random.seed(42)
    
    for crop_name, profile in CROP_PROFILES.items():
        base = np.array(profile["base"])
        spread = np.array(profile["spread"])
        
        for _ in range(samples_per_crop):
            # Apply gaussian noise
            sample = np.random.normal(base, spread)
            
            # Clip bounds logically (indices are usually -1 to 1, month is 1 to 12)
            sample[0] = np.clip(sample[0], 0, 1)      # NDVI_max
            sample[1] = np.clip(sample[1], 0, 1)      # NDVI_mean
            sample[2] = np.clip(sample[2], 0, 0.5)    # NDVI_std
            sample[3] = np.clip(np.round(sample[3]), 1, 12)  # Peak Month
            sample[4] = np.clip(sample[4], 0, 1)      # EVI_max
            sample[5] = np.clip(sample[5], -1, 1)     # NDWI_max
            sample[6] = np.clip(sample[6], 0, 1)      # SAVI_max
            sample[7] = np.clip(sample[7], 0, 1)      # GNDVI_max
            
            data.append(sample)
            labels.append(crop_name)
            
    columns = [
        "ndvi_max", "ndvi_mean", "ndvi_std", "peak_month", 
        "evi_max", "ndwi_max", "savi_max", "gndvi_max"
    ]
    df = pd.DataFrame(data, columns=columns)
    df["crop_label"] = labels
    return df

if __name__ == "__main__":
    df = generate_synthetic_dataset(10)
    print("Generated dummy dataset sample:")
    print(df.head())
