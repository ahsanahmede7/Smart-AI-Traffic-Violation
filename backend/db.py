import os
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv()
db = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))[os.getenv("DB_NAME", "smart_traffic")]
violations, users = db.violations, db.users  # also: vehicles, traffic_data, locations (create when needed)
