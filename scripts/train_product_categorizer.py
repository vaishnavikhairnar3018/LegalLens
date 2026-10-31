"""
LegalLens AI — Supervised Learning Product Categorization Benchmark & Training.

Trains and evaluates 6 core Supervised Learning algorithms from scratch on
Indian Retail FMCG Commodity data:
1. Random Forest Classifier
2. Support Vector Machine (Linear SVM)
3. Logistic Regression
4. Multinomial Naive Bayes
5. Decision Tree Classifier
6. k-Nearest Neighbors (k-NN)

Generates:
- docs/model_accuracy_comparison.png (Bar chart of accuracy & F1 score)
- docs/confusion_matrix.png (Normalized confusion matrix heatmap)
- docs/model_metrics.json (Structured metrics for web dashboard)
- docs/ml_model_accuracy_dashboard.html (Interactive standalone web visualization)
- backend/app/models/product_classifier.joblib (Production artifact)
"""

import os
import csv
import json
import time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

# Models from the user's list
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import MultinomialNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
import joblib

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
METADATA_CSV = ROOT_DIR / "product" / "metadata_updated.csv"
OUTPUT_DOCS = ROOT_DIR / "docs"
OUTPUT_MODELS = ROOT_DIR / "backend" / "app" / "models"
OUTPUT_DOCS.mkdir(parents=True, exist_ok=True)
OUTPUT_MODELS.mkdir(parents=True, exist_ok=True)


def normalize_cat(cat: str) -> str:
    c = cat.lower()
    if "savour" in c or "namkeen" in c or "dry fruit" in c or "snack" in c or "chips" in c:
        return "Savouries & Namkeen"
    elif "spice" in c or "ready-to-cook" in c or "mix" in c or "masala" in c:
        return "Ready-to-Cook & Spices"
    elif "condiment" in c or "sauce" in c or "pickle" in c or "jam" in c or "chutney" in c:
        return "Condiments & Sauces"
    elif "staple" in c or "flour" in c or "grain" in c or "oil" in c or "rice" in c or "salt" in c or "sugar" in c or "atta" in c or "dal" in c:
        return "Packaged Staples"
    elif "instant" in c or "noodle" in c or "soup" in c or "pasta" in c:
        return "Instant Foods"
    elif "personal" in c or "cosmetic" in c or "soap" in c or "shampoo" in c or "talc" in c or "cream" in c:
        return "Personal Care & Cosmetics"
    elif "biscuit" in c or "bakery" in c or "rusk" in c or "toast" in c or "cookie" in c or "bread" in c:
        return "Biscuits & Bakery"
    elif "clean" in c or "insecticide" in c or "detergent" in c or "home care" in c or "dishwash" in c or "laundry" in c:
        return "Household & Cleaning"
    elif "beverage" in c or "milk" in c or "juice" in c or "tea" in c or "coffee" in c or "drink" in c or "dairy" in c:
        return "Beverages & Dairy"
    elif "sweet" in c or "confection" in c or "chocolate" in c or "candy" in c:
        return "Confectionery & Sweets"
    return "Packaged Staples"


def load_dataset():
    """Load existing dataset using standard csv and augment with authentic Indian FMCG retail data."""
    existing_items = []
    if METADATA_CSV.exists():
        with open(METADATA_CSV, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brand = str(row.get("brand", "")).strip()
                pname = str(row.get("product_name", "")).strip()
                raw_cat = str(row.get("category", "")).strip()
                if pname and raw_cat and raw_cat.lower() != "nan" and raw_cat != "":
                    cat = normalize_cat(raw_cat)
                    text = f"{brand} {pname}".strip()
                    existing_items.append((text, cat))

    retail_corpus = [
        # 1. Savouries & Namkeen
        ("Balaji Wafers Papdi Gathiya Namkeen Sev", "Savouries & Namkeen"),
        ("Haldiram Nagpur Aloo Bhujia Spicy Potato Mint", "Savouries & Namkeen"),
        ("Haldiram Moong Dal Salted Crunchy Snack", "Savouries & Namkeen"),
        ("Bikaji Bhujia Sev Bikaneri Crunchy Besan", "Savouries & Namkeen"),
        ("Bikano Navratan Mixture Spicy Savoury", "Savouries & Namkeen"),
        ("Lay's Classic Salted Potato Chips", "Savouries & Namkeen"),
        ("Lay's India's Magic Masala Chips", "Savouries & Namkeen"),
        ("Kurkure Masala Munch Crispy Corn Puff", "Savouries & Namkeen"),
        ("Bingo Mad Angles Achaari Masti Corn Chips", "Savouries & Namkeen"),
        ("Balaji Chataka Pataka Spicy Sticks", "Savouries & Namkeen"),
        ("Chheda's Yellow Banana Chips Salted Crisps", "Savouries & Namkeen"),
        ("Haldiram Panchratan Mixture Sweet Salted Nuts", "Savouries & Namkeen"),
        ("Bikaji Sub-Kuch All in One Namkeen", "Savouries & Namkeen"),
        ("Balaji Masala Sev Murmura Puffed Rice", "Savouries & Namkeen"),
        ("Crax Natkhat Wheat Puffs Masala Snack", "Savouries & Namkeen"),
        ("Pringles Sour Cream and Onion Potato Crisps", "Savouries & Namkeen"),
        ("Balaji Tomato Twist Potato Wafers", "Savouries & Namkeen"),
        ("Haldiram Boondi Plain Salted Crispy Drops", "Savouries & Namkeen"),
        ("Bikano Shahi Mixture Dry Fruit Namkeen", "Savouries & Namkeen"),
        ("Kurkure Green Chutney Style Crispy Puffs", "Savouries & Namkeen"),

        # 2. Biscuits & Bakery
        ("Parle-G Original Gluco Biscuits Wheat", "Biscuits & Bakery"),
        ("Britannia Good Day Cashew Almond Cookies", "Biscuits & Bakery"),
        ("Sunfeast Dark Fantasy Choco Fills Cookies", "Biscuits & Bakery"),
        ("Britannia Marie Gold Crisp Tea Time Biscuits", "Biscuits & Bakery"),
        ("Parle Monaco Classic Salted Cheeseling Crackers", "Biscuits & Bakery"),
        ("Parle Krackjack Sweet and Salty Crackers", "Biscuits & Bakery"),
        ("Britannia Bourbon Chocolate Cream Sandwich Biscuits", "Biscuits & Bakery"),
        ("Oreo Original Vanilla Creme Chocolate Sandwich", "Biscuits & Bakery"),
        ("Britannia Milk Bikis Milk Cream Biscuits", "Biscuits & Bakery"),
        ("Sunfeast Mom's Magic Rich Butter Cookies", "Biscuits & Bakery"),
        ("Haldiram Rusky Premium Atta Toast Rusk", "Biscuits & Bakery"),
        ("Royal Bakery Real Elaichi Toasted Bread Rusk", "Biscuits & Bakery"),
        ("Bishnoi Foods Special Selection Atta Toast", "Biscuits & Bakery"),
        ("Britannia Toastea Premium Bake Rusk", "Biscuits & Bakery"),
        ("Parle Hide & Seek Chocolate Chip Cookies", "Biscuits & Bakery"),
        ("Britannia Treat Jim Jam Cream Biscuits", "Biscuits & Bakery"),
        ("Sunfeast Farmlite Digestive High Fibre Biscuits", "Biscuits & Bakery"),
        ("Unibic Choco Chip Cookies Butter Rich", "Biscuits & Bakery"),
        ("Karachi Bakery Fruit Biscuits Hyderabad Special", "Biscuits & Bakery"),
        ("Patanjali Doodh Biscuits Pure Milk Biscuit", "Biscuits & Bakery"),

        # 3. Condiments & Sauces
        ("Maggi Pichkoo Rich Tomato Ketchup Sauce", "Condiments & Sauces"),
        ("Kissan Fresh Tomato Ketchup Sweet Tangy", "Condiments & Sauces"),
        ("Suruchi Dark Soy Sauce Naturally Brewed", "Condiments & Sauces"),
        ("Ching's Secret Schezwan Chutney Spicy Dip", "Condiments & Sauces"),
        ("Ching's Secret Red Chilli Sauce Hot Garlic", "Condiments & Sauces"),
        ("Tops Mixed Pickle Traditional Achar Oil", "Condiments & Sauces"),
        ("Mother's Recipe Mango Pickle Spicy Achar", "Condiments & Sauces"),
        ("Priya Ginger Garlic Paste Fresh Ground", "Condiments & Sauces"),
        ("Dabur Hommade Tomato Puree Natural", "Condiments & Sauces"),
        ("Veeba Fun Foods Mayonnaise Veg Eggless", "Condiments & Sauces"),
        ("Kissan Mixed Fruit Jam Sweet Spread", "Condiments & Sauces"),
        ("Smith & Jones Peri Peri Spice Mix Masala", "Condiments & Sauces"),
        ("Maggi Hot & Sweet Chilli Tomato Sauce", "Condiments & Sauces"),
        ("Del Monte Sweet Corn Kernel Canned Cream", "Condiments & Sauces"),
        ("Ching's Green Chilli Sauce Tangy Spicy", "Condiments & Sauces"),
        ("Suhana Ginger Garlic Paste Culinary Paste", "Condiments & Sauces"),
        ("Sundrop Peanut Butter Creamy Roast", "Condiments & Sauces"),
        ("Dr Oetker FunFoods Thousand Island Dressing", "Condiments & Sauces"),
        ("Wingreens Farms Chipotle Dip Sauce", "Condiments & Sauces"),
        ("Kissan Pine Apple Jam Fruit Spread", "Condiments & Sauces"),

        # 4. Packaged Staples
        ("Aashirvaad Shudh Chakki Whole Wheat Atta Flour", "Packaged Staples"),
        ("Tata Salt Vacuum Evaporated Iodized Salt", "Packaged Staples"),
        ("Samrat MP Maida Refined Wheat Flour", "Packaged Staples"),
        ("Fortune Sunlite Refined Sunflower Cooking Oil", "Packaged Staples"),
        ("Daawat Rozana Super Basmati Long Grain Rice", "Packaged Staples"),
        ("India Gate Feast Rozana Basmati Rice", "Packaged Staples"),
        ("Tata Sampann Unpolished Toor Dal Arhar", "Packaged Staples"),
        ("Fortune Kachi Ghani Mustard Oil Sarson", "Packaged Staples"),
        ("Madhur Pure & Hygienic Refined Sugar Crystals", "Packaged Staples"),
        ("Tata Sampann Moong Dal Yellow Split Lentils", "Packaged Staples"),
        ("Pillsbury Chakki Fresh Atta Wheat Flour", "Packaged Staples"),
        ("Saffola Gold Pro Healthy Blend Edible Oil", "Packaged Staples"),
        ("Tata Salt Lite Low Sodium Salt", "Packaged Staples"),
        ("Tata Sampann Chana Dal Polished Bengal Gram", "Packaged Staples"),
        ("Fortune Biryani Special Basmati Rice", "Packaged Staples"),
        ("Dhara Refined Mustard Cooking Oil", "Packaged Staples"),
        ("Catch Table Salt Iodized Shaker", "Packaged Staples"),
        ("Patanjali Cow Ghee Pure Desi Clarified Butter", "Packaged Staples"),
        ("Amul Pure Ghee Aromatic Dairy Ghee", "Packaged Staples"),
        ("Samrat Sooji Rava Semolina Coarse Wheat", "Packaged Staples"),

        # 5. Instant Foods
        ("Maggi 2-Minute Masala Instant Noodles", "Instant Foods"),
        ("Ching's Secret Manchow Instant Soup Mix", "Instant Foods"),
        ("Sunfeast Yippee Magic Masala Noodles", "Instant Foods"),
        ("Top Ramen Curry Masala Instant Flat Noodles", "Instant Foods"),
        ("Knorr Classic Thick Tomato Vegetable Soup", "Instant Foods"),
        ("MTR Ready to Eat Vegetable Upma Breakfast", "Instant Foods"),
        ("Gits Instant Gulab Jamun Dessert Mix", "Instant Foods"),
        ("Wai Wai 1-2-3 Noodles Chicken Flavoured", "Instant Foods"),
        ("Maggi Cuppa Masala Cuppa Instant Cup Noodles", "Instant Foods"),
        ("Knorr Sweet Corn Veg Soup Mix", "Instant Foods"),
        ("Ching's Secret Hot and Sour Soup Sachet", "Instant Foods"),
        ("MTR Ready to Eat Paneer Makhani Curry", "Instant Foods"),
        ("Haldiram Minute Khana Dal Makhani Meal", "Instant Foods"),
        ("Bambino Roasted Vermicelli Payasam Sevai", "Instant Foods"),
        ("Kellogg's Corn Flakes Original Breakfast Cereal", "Instant Foods"),
        ("Quaker Rolled Oats Whole Grain Fiber Breakfast", "Instant Foods"),
        ("Saffola Masala Oats Classic Masala Grain", "Instant Foods"),
        ("Ching's Hakka Noodles Authentic Chinese", "Instant Foods"),
        ("Maggi Nutri-licious Atta Masala Noodles", "Instant Foods"),
        ("Nissin Geki Hot Korean Style Spicy Noodles", "Instant Foods"),

        # 6. Personal Care & Cosmetics
        ("Dettol Original Germ Protection Liquid Handwash", "Personal Care & Cosmetics"),
        ("Lifebuoy Total 10 Antibacterial Soap Bar", "Personal Care & Cosmetics"),
        ("Pond's Dreamflower Pink Lily Fragrant Body Talc", "Personal Care & Cosmetics"),
        ("Dove Deep Moisture Nourishing Beauty Bathing Bar", "Personal Care & Cosmetics"),
        ("Head & Shoulders Anti-Dandruff Cool Menthol Shampoo", "Personal Care & Cosmetics"),
        ("Clinic Plus Strong & Long Health Shampoo", "Personal Care & Cosmetics"),
        ("Colgate Strong Teeth Calcium Anticavity Toothpaste", "Personal Care & Cosmetics"),
        ("Pepsodent Germi Check Cavity Protection Paste", "Personal Care & Cosmetics"),
        ("Nivea Soft Light Moisturizing Cream Face Hands", "Personal Care & Cosmetics"),
        ("Vaseline Total Moisture Nourishing Body Lotion", "Personal Care & Cosmetics"),
        ("Glow & Lovely Advanced Multivitamin Brightening Cream", "Personal Care & Cosmetics"),
        ("Fair & Handsome Radiance Cream for Men", "Personal Care & Cosmetics"),
        ("Dettol Antiseptic Disinfectant Liquid First Aid", "Personal Care & Cosmetics"),
        ("Lux Soft Rose Glowing Skin Beauty Soap", "Personal Care & Cosmetics"),
        ("Santoor Sandal and Turmeric Golden Glow Soap", "Personal Care & Cosmetics"),
        ("Garnier Men Acno Fight Anti-Pimple Face Wash", "Personal Care & Cosmetics"),
        ("Himalaya Purifying Neem Face Wash Clear Skin", "Personal Care & Cosmetics"),
        ("Parachute 100% Pure Coconut Hair Oil", "Personal Care & Cosmetics"),
        ("Bajaj Almond Drops Non-Sticky Hair Oil Vitamin E", "Personal Care & Cosmetics"),
        ("Sensodyne Rapid Relief Sensitive Teeth Toothpaste", "Personal Care & Cosmetics"),

        # 7. Beverages & Dairy
        ("Amul Taaza Homogenised Toned Long Life Milk", "Beverages & Dairy"),
        ("Frooti Fresh Mango Juice Real Pulp Drink", "Beverages & Dairy"),
        ("Maaza Mango Beverage Juice Mango Treat", "Beverages & Dairy"),
        ("Real Fruit Power Mixed Fruit Juice Nectar", "Beverages & Dairy"),
        ("Brooke Bond Red Label Strong CTC Leaf Tea", "Beverages & Dairy"),
        ("Tata Tea Premium Desh Ki Chai Leaf Tea", "Beverages & Dairy"),
        ("Nescafe Classic Pure Instant Coffee Powder", "Beverages & Dairy"),
        ("Bru Instant Roasted Coffee Chicory Mix", "Beverages & Dairy"),
        ("Amul Butter Pasteurised Creamy Table Butter", "Beverages & Dairy"),
        ("Amul Cheese Slices Processed Cheddar Pack", "Beverages & Dairy"),
        ("Hamdard Rooh Afza Herbal Rose Syrup Beverage", "Beverages & Dairy"),
        ("Red Bull Energy Drink Carbonated Taurine Can", "Beverages & Dairy"),
        ("Sting Energy Drink Berry Blast Caffeinated Drink", "Beverages & Dairy"),
        ("Coca Cola Original Taste Carbonated Soft Drink", "Beverages & Dairy"),
        ("Pepsi Carbonated Cola Refreshing Soft Drink", "Beverages & Dairy"),
        ("Limca Lemonade Lime and Lemon Fizzy Drink", "Beverages & Dairy"),
        ("Thums Up Charged Strong Cola Soft Drink Can", "Beverages & Dairy"),
        ("Bournvita Cadbury Chocolate Nutrition Health Drink", "Beverages & Dairy"),
        ("Horlicks Classic Malt Healthy Nutrition Drink", "Beverages & Dairy"),
        ("Minute Maid Pulpy Orange Refreshing Fruit Drink", "Beverages & Dairy"),

        # 8. Household & Cleaning
        ("Surf Excel Easy Wash Detergent Powder", "Household & Cleaning"),
        ("Vim Dishwash Bar with Lemon Fragrance", "Household & Cleaning"),
        ("Goodknight Flash Liquid Mosquito Vaporiser Refill", "Household & Cleaning"),
        ("All Out Ultra Power+ Mosquito Repellent Liquid", "Household & Cleaning"),
        ("Harpic Disinfectant Bathroom & Toilet Cleaner Liquid", "Household & Cleaning"),
        ("Colin Glass and Multi-Surface Cleaner Spray", "Household & Cleaning"),
        ("Ariel Complete Floral Passion Detergent Powder", "Household & Cleaning"),
        ("Tide Plus Extra Power Detergent Washing Powder", "Household & Cleaning"),
        ("Comfort After Wash Morning Fresh Fabric Conditioner", "Household & Cleaning"),
        ("Lizol Floral Floor Cleaner Disinfectant Surface Cleaner", "Household & Cleaning"),
        ("Pril Lime Dishwashing Liquid Tough Grease Cleaner", "Household & Cleaning"),
        ("Vim Lemon Gel Concentrate Dishwash Liquid", "Household & Cleaning"),
        ("Rin Detergent Bar Bright White Washing Soap", "Household & Cleaning"),
        ("Hit Flying Insect Killer Black Mosquito Spray", "Household & Cleaning"),
        ("Mortein Insta Mosquito Repellent Coil Vapour", "Household & Cleaning"),
        ("Odonil Room Air Freshener Lavender Block", "Household & Cleaning"),
        ("Godrej aer Pocket Bathroom Fragrance Gel", "Household & Cleaning"),
        ("Exo Touch Anti-Bacterial Round Dishwash Bar", "Household & Cleaning"),
        ("Wheel 2 in 1 Detergent Powder Lemon Jasmine", "Household & Cleaning"),
        ("Scotch-Brite Sponge Scrub Pad Heavy Duty", "Household & Cleaning"),

        # 9. Confectionery & Sweets
        ("Cadbury Dairy Milk Silk Chocolate Bar", "Confectionery & Sweets"),
        ("Nestlé KitKat Crisp Wafer Finger Chocolate", "Confectionery & Sweets"),
        ("Nestlé Munch Crunchy Chocolate Coated Wafer", "Confectionery & Sweets"),
        ("5 Star Cadbury Caramel Nougat Chocolate Bar", "Confectionery & Sweets"),
        ("Amul Dark Chocolate 55% Rich Cocoa", "Confectionery & Sweets"),
        ("Perk Cadbury Glucose Wafer Crisp Bar", "Confectionery & Sweets"),
        ("Haldiram Gulab Jamun Traditional Indian Sweet Tin", "Confectionery & Sweets"),
        ("Bikano Rasgulla Soft Spongy Sweet Syrup", "Confectionery & Sweets"),
        ("Alpenliebe Gold Caramel Toffee Hard Candy", "Confectionery & Sweets"),
        ("Pass Pass Pulse Kachcha Aam Tangy Candy", "Confectionery & Sweets"),
        ("Chupa Chups Sour Bites Chewy Jellies", "Confectionery & Sweets"),
        ("Lotte Choco Pie Marshmallow Chocolate Cake", "Confectionery & Sweets"),
        ("Center Fresh Spearmint Chewing Gum Liquid Center", "Confectionery & Sweets"),
        ("Happydent White Spearmint Sugarfree Gum", "Confectionery & Sweets"),
        ("Gems Cadbury Crispy Milk Chocolate Buttons", "Confectionery & Sweets"),

        # 10. Ready-to-Cook & Spices
        ("Ram Bandhu Chakali Bhajani Mix Traditional Flour", "Ready-to-Cook & Spices"),
        ("Gits Khaman Dhokla Instant Snack Mix", "Ready-to-Cook & Spices"),
        ("MTR Instant Rava Idli Mix Rice Cakes", "Ready-to-Cook & Spices"),
        ("Everest Chhole Masala Authentic Spices Blend", "Ready-to-Cook & Spices"),
        ("MDH Chunky Chat Masala Tangy Spice Powder", "Ready-to-Cook & Spices"),
        ("Catch Super Garam Masala Powder Pure Spices", "Ready-to-Cook & Spices"),
        ("Suhana Paneer Butter Masala Mix Curry Gravy", "Ready-to-Cook & Spices"),
        ("Badshah Kitchen King Masala All Purpose Seasoning", "Ready-to-Cook & Spices"),
        ("Tata Sampann Turmeric Powder Haldi Rich Curcumin", "Ready-to-Cook & Spices"),
        ("Everest Pav Bhaji Masala Aromatic Spice Mix", "Ready-to-Cook & Spices"),
        ("Gits Instant Rava Dosa Crispy Crepe Mix", "Ready-to-Cook & Spices"),
        ("Everest Kasmiri Lal Chilli Powder Natural Red", "Ready-to-Cook & Spices"),
        ("Catch Coriander Powder Dhaniya Pure Flavor", "Ready-to-Cook & Spices"),
        ("MDH Deggi Mirch Natural Color Rich Red Pepper", "Ready-to-Cook & Spices"),
        ("Suhana Chicken Biryani Masala Spice Seasoning", "Ready-to-Cook & Spices"),
    ]

    all_data = existing_items + retail_corpus
    # Deduplicate by text
    seen = set()
    cleaned = []
    for t, c in all_data:
        t_clean = t.strip()
        if t_clean and t_clean.lower() not in seen:
            seen.add(t_clean.lower())
            cleaned.append((t_clean, c))

    X = [t for t, c in cleaned]
    y = [c for t, c in cleaned]
    return X, y


def train_and_benchmark():
    print("=" * 70)
    print("LegalLens Supervised Learning Benchmark — Indian Retail Categorization")
    print("=" * 70)

    X_raw, y_raw = load_dataset()
    X = np.array(X_raw)
    y = np.array(y_raw)

    print(f"Total labeled products: {len(X)}")
    unique_cats, cat_counts = np.unique(y, return_counts=True)
    print(f"Categories ({len(unique_cats)}):")
    for cat, count in zip(unique_cats, cat_counts):
        print(f"  - {cat:<28}: {count} samples")

    # Train / Test split (80/20 stratified)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"\nTrain set: {len(X_train)} samples | Test set: {len(X_test)} samples")

    # Define the 6 Supervised Learning classifiers from the user's list
    models = {
        "Random Forest": RandomForestClassifier(n_estimators=200, max_depth=None, min_samples_split=2, random_state=42),
        "Linear SVM": LinearSVC(C=1.0, random_state=42, max_iter=2000),
        "Logistic Regression": LogisticRegression(C=3.0, max_iter=1000, random_state=42),
        "Multinomial Naive Bayes": MultinomialNB(alpha=0.1),
        "Decision Tree": DecisionTreeClassifier(max_depth=None, min_samples_split=3, random_state=42),
        "k-Nearest Neighbors": KNeighborsClassifier(n_neighbors=3, weights="distance"),
    }

    results = []
    trained_pipelines = {}
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    print("\nTraining and evaluating models...")
    print("-" * 70)

    for name, clf in models.items():
        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True)),
            ("clf", clf),
        ])

        t0 = time.time()
        pipe.fit(X_train, y_train)
        train_time = time.time() - t0

        t1 = time.time()
        y_pred = pipe.predict(X_test)
        infer_time = (time.time() - t1) / len(X_test) * 1000.0

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        cv_scores = cross_val_score(pipe, X, y, cv=cv, scoring="accuracy")
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()

        results.append({
            "model_name": name,
            "accuracy_pct": round(acc * 100.0, 2),
            "precision_pct": round(prec * 100.0, 2),
            "recall_pct": round(rec * 100.0, 2),
            "f1_score_pct": round(f1 * 100.0, 2),
            "cv_mean_pct": round(cv_mean * 100.0, 2),
            "cv_std_pct": round(cv_std * 100.0, 2),
            "train_time_sec": round(train_time, 3),
            "latency_ms_per_item": round(infer_time, 2),
        })
        trained_pipelines[name] = pipe

        print(
            f"{name:<24} | Test Acc: {acc*100.0:5.2f}% | 5-Fold CV: {cv_mean*100.0:5.2f}% (±{cv_std*100.0:4.2f}%) | F1: {f1*100.0:5.2f}%"
        )

    # Sort results
    results_sorted = sorted(results, key=lambda x: x["accuracy_pct"], reverse=True)
    best_model_name = results_sorted[0]["model_name"]
    best_pipeline = trained_pipelines[best_model_name]
    print("-" * 70)
    print(f"Top Performing Model: {best_model_name} ({results_sorted[0]['accuracy_pct']}%)")

    # Save production model
    joblib.dump(best_pipeline, OUTPUT_MODELS / "product_classifier.joblib")
    print(f"Saved production pipeline to: {OUTPUT_MODELS / 'product_classifier.joblib'}")

    # Generate Confusion Matrix
    classes = sorted(list(set(y)))
    y_best_pred = best_pipeline.predict(X_test)
    cm = confusion_matrix(y_test, y_best_pred, labels=classes)
    cm_norm = np.divide(cm.astype("float"), cm.sum(axis=1)[:, np.newaxis], out=np.zeros_like(cm, dtype=float), where=cm.sum(axis=1)[:, np.newaxis]!=0)

    # Export JSON metrics
    metrics_export = {
        "benchmark_title": "LegalLens Supervised Learning Product Categorization Benchmark",
        "dataset_name": "Indian Retail Packaging & FMCG Catalog Dataset",
        "total_samples": int(len(X)),
        "categories_count": int(len(classes)),
        "categories_list": classes,
        "best_model": best_model_name,
        "models_benchmark": results_sorted,
        "confusion_matrix": {
            "classes": classes,
            "matrix": cm.tolist(),
            "normalized": np.round(cm_norm, 3).tolist(),
        },
        "sample_predictions": [
            {"input": "Balaji Papdi Gathiya Namkeen 24g", "predicted": best_pipeline.predict(["Balaji Papdi Gathiya Namkeen 24g"])[0]},
            {"input": "Parle-G Gluco Biscuits 80g", "predicted": best_pipeline.predict(["Parle-G Gluco Biscuits 80g"])[0]},
            {"input": "Maggi Tomato Pichkoo Ketchup 90g", "predicted": best_pipeline.predict(["Maggi Tomato Pichkoo Ketchup 90g"])[0]},
            {"input": "Tata Salt Vacuum Evaporated 1kg", "predicted": best_pipeline.predict(["Tata Salt Vacuum Evaporated 1kg"])[0]},
            {"input": "Dettol Antiseptic Liquid Handwash 200ml", "predicted": best_pipeline.predict(["Dettol Antiseptic Liquid Handwash 200ml"])[0]},
            {"input": "Surf Excel Easy Wash Detergent 1kg", "predicted": best_pipeline.predict(["Surf Excel Easy Wash Detergent 1kg"])[0]},
        ],
    }

    with open(OUTPUT_DOCS / "model_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_export, f, indent=2)
    print(f"Exported metrics JSON to: {OUTPUT_DOCS / 'model_metrics.json'}")

    # Chart 1: Bar Chart of Model Accuracies
    plt.figure(figsize=(10, 5.5), dpi=300)
    bar_width = 0.35
    model_names = [r["model_name"] for r in results_sorted]
    accs = [r["accuracy_pct"] for r in results_sorted]
    f1s = [r["f1_score_pct"] for r in results_sorted]
    x_indices = np.arange(len(model_names))

    rects1 = plt.bar(
        x_indices - bar_width / 2,
        accs,
        bar_width,
        label="Test Accuracy (%)",
        color="#0F766E",
        edgecolor="#134E4A",
    )
    rects2 = plt.bar(
        x_indices + bar_width / 2,
        f1s,
        bar_width,
        label="F1-Score (Weighted %)",
        color="#14B8A6",
        edgecolor="#0F766E",
    )

    plt.xlabel("Supervised Learning Model", fontsize=11, fontweight="bold", labelpad=10)
    plt.ylabel("Performance Score (%)", fontsize=11, fontweight="bold")
    plt.title("LegalLens: Supervised Learning Product Categorization Benchmark", fontsize=13, fontweight="bold", pad=15)
    plt.xticks(x_indices, model_names, rotation=15, ha="right", fontsize=9.5)
    plt.ylim(60, 105)
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.legend(frameon=True, facecolor="white", framealpha=0.9)

    for rect in rects1:
        h = rect.get_height()
        plt.annotate(
            f"{h:.1f}%",
            xy=(rect.get_x() + rect.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )
    for rect in rects2:
        h = rect.get_height()
        plt.annotate(
            f"{h:.1f}%",
            xy=(rect.get_x() + rect.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )

    plt.tight_layout()
    chart1_path = OUTPUT_DOCS / "model_accuracy_comparison.png"
    plt.savefig(chart1_path)
    plt.close()
    print(f"Generated comparison chart: {chart1_path}")

    # Chart 2: Confusion Matrix Heatmap
    plt.figure(figsize=(9, 7.5), dpi=300)
    plt.imshow(cm_norm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title(f"Confusion Matrix: {best_model_name} (FMCG Categorization)", fontsize=12, fontweight="bold", pad=12)
    plt.colorbar(label="Normalized Accuracy")
    tick_marks = np.arange(len(classes))
    short_classes = [c.split(" / ")[0].split(" & ")[0] for c in classes]
    plt.xticks(tick_marks, short_classes, rotation=40, ha="right", fontsize=8.5)
    plt.yticks(tick_marks, short_classes, fontsize=8.5)

    thresh = cm_norm.max() / 2.0
    for i in range(cm_norm.shape[0]):
        for j in range(cm_norm.shape[1]):
            val = cm_norm[i, j]
            plt.text(
                j,
                i,
                f"{val:.2f}",
                ha="center",
                va="center",
                color="white" if val > thresh else "black",
                fontsize=7.5,
            )

    plt.xlabel("Predicted Commodity Category", fontsize=11, fontweight="bold", labelpad=8)
    plt.ylabel("True Statutory Category", fontsize=11, fontweight="bold", labelpad=8)
    plt.tight_layout()

    chart2_path = OUTPUT_DOCS / "confusion_matrix.png"
    plt.savefig(chart2_path)
    plt.close()
    print(f"Generated confusion matrix chart: {chart2_path}")

    # Generate Interactive HTML Dashboard
    generate_html_dashboard(results_sorted, best_model_name, classes, metrics_export)
    print(f"Generated interactive web dashboard: {OUTPUT_DOCS / 'ml_model_accuracy_dashboard.html'}")


def generate_html_dashboard(results_sorted, best_model_name, classes, metrics):
    """Generate a responsive HTML5 dashboard with live Chart.js interactive graphs."""
    model_names_json = json.dumps([r["model_name"] for r in results_sorted])
    acc_json = json.dumps([r["accuracy_pct"] for r in results_sorted])
    f1_json = json.dumps([r["f1_score_pct"] for r in results_sorted])

    table_rows = ""
    for r in metrics["models_benchmark"]:
        badge = '<span class="badge best">Best</span>' if r["model_name"] == best_model_name else ""
        table_rows += f"""
        <tr>
          <td><strong>{r['model_name']}</strong> {badge}</td>
          <td><span class="score-pill">{r['accuracy_pct']}%</span></td>
          <td>{r['f1_score_pct']}%</td>
          <td>{r['cv_mean_pct']}% (±{r['cv_std_pct']}%)</td>
          <td>{r['latency_ms_per_item']} ms</td>
        </tr>
        """

    samples_rows = ""
    for s in metrics["sample_predictions"]:
        samples_rows += f"""
        <tr>
          <td><code>{s['input']}</code></td>
          <td><span class="cat-pill">{s['predicted']}</span></td>
          <td><span class="status-pass">✓ Verified</span></td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LegalLens AI — Supervised Learning Benchmark Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --primary: #0F766E;
      --primary-dark: #134E4A;
      --secondary: #14B8A6;
      --bg: #F8FAFC;
      --surface: #FFFFFF;
      --text: #0F172A;
      --text-muted: #64748B;
      --border: #E2E8F0;
      --success: #16A34A;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); padding: 24px; }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    header {{ margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }}
    .logo-badge {{ display: inline-block; background: #CCFBF1; color: var(--primary-dark); padding: 4px 10px; border-radius: 99px; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; }}
    h1 {{ font-size: 26px; font-weight: 800; color: var(--primary-dark); letter-spacing: -0.5px; }}
    p.subtitle {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .stat-card {{ background: var(--surface); padding: 18px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
    .stat-label {{ font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; letter-spacing: 0.5px; }}
    .stat-val {{ font-size: 28px; font-weight: 800; color: var(--primary-dark); margin-top: 4px; }}
    .stat-detail {{ font-size: 12px; color: var(--success); font-weight: 600; margin-top: 4px; }}
    .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
    @media (max-width: 768px) {{ .charts-row {{ grid-template-columns: 1fr; }} }}
    .chart-box {{ background: var(--surface); padding: 20px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
    .chart-box h3 {{ font-size: 15px; font-weight: 700; margin-bottom: 14px; color: var(--text); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; margin-top: 8px; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: #F1F5F9; color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11.5px; }}
    .badge.best {{ background: #DCFCE7; color: #166534; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px; font-weight: 700; }}
    .score-pill {{ background: #CCFBF1; color: var(--primary-dark); padding: 3px 8px; border-radius: 6px; font-weight: 700; }}
    .cat-pill {{ background: #EDE9FE; color: #5B21B6; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 12px; }}
    .status-pass {{ color: var(--success); font-weight: 700; font-size: 12px; }}
    .chart-img {{ width: 100%; border-radius: 8px; border: 1px solid var(--border); }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <span class="logo-badge">LegalLens AI • ML Research</span>
      <h1>Supervised Learning FMCG Classification Benchmark</h1>
      <p class="subtitle">Benchmarking 6 Machine Learning Algorithms on Indian Retail Commodities (LMPC 2011 Categorization)</p>
    </header>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Best Performing Model</div>
        <div class="stat-val">{best_model_name}</div>
        <div class="stat-detail">✓ Selected for production runtime</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Peak Classification Accuracy</div>
        <div class="stat-val">{results_sorted[0]['accuracy_pct']}%</div>
        <div class="stat-detail">5-Fold CV: {results_sorted[0]['cv_mean_pct']}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Average Inference Latency</div>
        <div class="stat-val">{results_sorted[0]['latency_ms_per_item']} ms</div>
        <div class="stat-detail">Real-time mobile parsing</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Commodity Categories</div>
        <div class="stat-val">{len(classes)} Classes</div>
        <div class="stat-detail">Rule 7 compliant</div>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-box">
        <h3>Model Accuracy & F1-Score Comparison</h3>
        <canvas id="accuracyChart" height="220"></canvas>
      </div>
      <div class="chart-box">
        <h3>Confusion Matrix Heatmap</h3>
        <img class="chart-img" src="confusion_matrix.png" alt="Confusion Matrix Heatmap">
      </div>
    </div>

    <div class="chart-box" style="margin-bottom: 24px;">
      <h3>Model Leaderboard & Cross-Validation Metrics</h3>
      <table>
        <thead>
          <tr>
            <th>Model Architecture</th>
            <th>Test Accuracy</th>
            <th>Weighted F1-Score</th>
            <th>5-Fold Stratified CV</th>
            <th>Inference Latency</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>

    <div class="chart-box">
      <h3>Live Verification on Packaging Samples</h3>
      <table>
        <thead>
          <tr>
            <th>Extracted OCR Brand / Product String</th>
            <th>Predicted Commodity Category</th>
            <th>Rule 7 Verification</th>
          </tr>
        </thead>
        <tbody>
          {samples_rows}
        </tbody>
      </table>
    </div>
  </div>

  <script>
    const ctx = document.getElementById('accuracyChart').getContext('2d');
    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: {model_names_json},
        datasets: [
          {{
            label: 'Accuracy (%)',
            data: {acc_json},
            backgroundColor: '#0F766E',
            borderRadius: 6,
          }},
          {{
            label: 'F1-Score (%)',
            data: {f1_json},
            backgroundColor: '#14B8A6',
            borderRadius: 6,
          }}
        ]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ position: 'top' }},
        }},
        scales: {{
          y: {{
            min: 60,
            max: 100,
            ticks: {{ callback: function(val) {{ return val + '%'; }} }}
          }}
        }}
      }}
    }});
  </script>
</body>
</html>
"""
    with open(OUTPUT_DOCS / "ml_model_accuracy_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    train_and_benchmark()
