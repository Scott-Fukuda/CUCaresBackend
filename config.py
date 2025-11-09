class StagingConfig:
    SQLALCHEMY_DATABASE_URI = "postgresql://staging_user:staging_pass@localhost:5433/cucares_staging"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class ProdDBConfig:
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://campus_cares_backend_user:vemaaSuFasSqN0OjfjKB0tyJ2v9jsTxe@dpg-d2o82k8dl3ps73d7rutg-a.ohio-postgres.render.com/campus_cares_backend"
    SQLALCHEMY_TRACK_MODIFICATIONS = False