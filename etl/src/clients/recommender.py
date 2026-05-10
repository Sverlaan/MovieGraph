# Data manipulation
import logging
import pandas as pd
from timeit import default_timer as timer
import pickle

logger = logging.getLogger(__name__)


class Recommender:
    """
    Recommender system using a pre-trained matrix factorization model.
    """

    def __init__(self, model_path):
        self.model = pickle.load(open(model_path, "rb"))
        self.slugs_in_model = list(self.model.item_id_map.keys())

    def preprocess(self, ratings_df, blacklists_df=pd.DataFrame()):
        """
        Preprocess the ratings before training.
        """
        timer_start = timer()

        # Filter out movies not in training set
        ratings_df = ratings_df[ratings_df["slug"].isin(self.slugs_in_model)]

        # Filter out movies that do not have ratings
        ratings_df = ratings_df[ratings_df["rating"].notnull()]

        # Augment ratings with fake low rating for blacklisted movies
        if blacklists_df is not None and not blacklists_df.empty:
            blacklists_df['rating'] = 2.0
            ratings_df = pd.concat([ratings_df, blacklists_df], ignore_index=True)

        # Scale to 0.5-5 for the model
        ratings_df['rating'] = ratings_df['rating'] / 2.0

        # Rename columns
        ratings_df = ratings_df.rename(columns={"username": "user_id", "slug": "item_id", "rating": "rating"})

        # pandas 3.0 defaults string columns to StringDtype, which rejects integer assignment.
        # The matrix_factorization library overwrites these columns with integer IDs internally,
        # so they must be object dtype.
        X = ratings_df[['user_id', 'item_id']].astype(object)
        return X, ratings_df['rating']

    def train_model(self, X_update, y_update, n_epochs=30, lr=0.01):
        """
        Retrain the model on new data by updating user embeddings.
        """
        # print("🔄 Retraining the model...", end="\r")
        timer_start = timer()
        self.model.update_users(
            X_update, y_update, lr=lr, n_epochs=n_epochs, verbose=0
        )
        logger.info("Retraining completed in %.2f seconds", timer() - timer_start)

    def get_recommendations_users(self, usernames: list, ratings_df, blacklists_df: pd.DataFrame = pd.DataFrame()):
        """
        Get recommendations based on a DataFrame of ratings.
        """
        X_update, y_update = self.preprocess(ratings_df, blacklists_df)

        # Retrain the model with new user data
        self.train_model(X_update, y_update)

        # Get recommendations
        start_time = timer()
        all_recs = []
        for username in usernames:
            user_recs = self.get_recommendations(username, X_update)
            all_recs.append(user_recs)

        logger.info("Recommendations generation completed in %.2f seconds", timer() - start_time)
        return pd.concat(all_recs, ignore_index=True)

    def get_recommendations(self, username, X_update):
        """
        Get recommendations based on a single user
        """
        start_time = timer()
        # print(f"🔄 Generating recommendations for user '{username}'...", end="\r")

        # Get recommendations
        items_known = X_update.query("user_id == @username")["item_id"]
        preds_df = self.model.recommend(user=username, items_known=items_known, amount=-1)

        # Put predictions back to 1-10 scale
        preds_df["rating_pred"] = preds_df["rating_pred"] * 2

        # rename columns for consistency
        preds_df = preds_df.rename(columns={"user_id": "username", "item_id": "slug", "rating_pred": "score"})

        return preds_df

    def get_embeddings(self):
        """
        Get the embeddings for all slugs in the model.
        """

        embeddings_df = pd.DataFrame({
            'slug': self.slugs_in_model,
            'mf_features': [self.model.item_features[i] for i in range(len(self.slugs_in_model))],
            'mf_bias': [self.model.item_biases[i] for i in range(len(self.slugs_in_model))]
        })
        return embeddings_df
