import os
from dotenv import load_dotenv

load_dotenv()

postgres_username = os.getenv('POSTGRES_USER')
postgres_password = os.getenv('POSTGRES_PASSWORD')
postgres_host = os.getenv('POSTGRES_HOST')
postgres_port = os.getenv('POSTGRES_PORT')
postgres_database = os.getenv('POSTGRES_DATABASE')

class Config:
    SQLALCHEMY_DATABASE_URI = f'postgresql://{postgres_username}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_database}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'my_secretest_key_you_cant_guess_123'


# import os
#
# class Config:
#     SQLALCHEMY_DATABASE_URI = 'postgresql://clocynhf_maaz:!rT#ui?#!iHK@localhost:5432/clocynhf_AdminPilotDb'
#     SQLALCHEMY_TRACK_MODIFICATIONS = False
#     SECRET_KEY = os.urandom(24)