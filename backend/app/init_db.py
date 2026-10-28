from app.db.database import Base, engine
from app.db import models  # Registers NetworkEvent with Base

Base.metadata.create_all(bind=engine)

print("NIDS database tables created successfully.")