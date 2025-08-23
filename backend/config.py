import os


GCP_PROJECT = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "throwpro"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "praxisforma-videos")
PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC", "throwpro-analyze")
FIRESTORE_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "throwSessions")


def as_dict() -> dict:
    return {
        "GCP_PROJECT": GCP_PROJECT,
        "GCS_BUCKET": GCS_BUCKET,
        "PUBSUB_TOPIC": PUBSUB_TOPIC,
        "FIRESTORE_COLLECTION": FIRESTORE_COLLECTION,
    }


