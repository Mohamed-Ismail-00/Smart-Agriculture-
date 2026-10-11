import os
import joblib
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from app.ml.synthetic_data import generate_synthetic_dataset

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "rf_crop_model.joblib")

def train_and_save_model():
    """Trains the Random Forest model on synthetic data and saves it to disk."""
    logger.info("Generating synthetic training dataset...")
    # Generate 500 samples for each of the 19 crops
    df = generate_synthetic_dataset(500)
    
    X = df.drop(columns=["crop_label"])
    y = df["crop_label"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    logger.info("Training Random Forest Classifier on %d samples...", len(X_train))
    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    
    # Evaluate
    accuracy = clf.score(X_test, y_test)
    logger.info(f"Model trained! Test Accuracy: {accuracy:.2f}")
    
    # Save the model
    joblib.dump(clf, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

def load_model() -> RandomForestClassifier:
    """Loads the trained model from disk, training it if it doesn't exist."""
    if not os.path.exists(MODEL_PATH):
        logger.info("Model not found. Triggering training...")
        train_and_save_model()
    return joblib.load(MODEL_PATH)

def predict_crop(features: list[float]) -> list[tuple[str, float]]:
    """
    Predicts the crop type based on a single feature array.
    Returns a list of (Crop Name, Probability) for probabilities > 10%.
    Features: [ndvi_max, ndvi_mean, ndvi_std, peak_month, evi_max, ndwi_max, savi_max, gndvi_max]
    """
    clf = load_model()
    
    # predict_proba expects a 2D array
    probs = clf.predict_proba([features])[0]
    classes = clf.classes_
    
    results = []
    for idx, prob in enumerate(probs):
        if prob > 0.10:  # Threshold for considering it a valid mix
            results.append((classes[idx], prob))
            
    # Sort by probability descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_and_save_model()
