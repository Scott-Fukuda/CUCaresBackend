class StagingConfig:
    SQLALCHEMY_DATABASE_URI = "postgresql://staging_user:staging_pass@localhost:5433/cucares_staging"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
