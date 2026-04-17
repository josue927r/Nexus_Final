import argparse
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from auth_models import User
from security import get_password_hash

# Aseguramos que la tabla exista
Base.metadata.create_all(bind=engine)

def create_user(username: str, password: str):
    db: Session = SessionLocal()
    
    # Verificar si el usuario ya existe
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        print(f"Error: El usuario '{username}' ya existe.")
        db.close()
        return

    # Crear nuevo usuario
    hashed_password = get_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()
    
    print(f"Éxito: Usuario '{username}' creado correctamente.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crear un nuevo usuario administrador en Nexus")
    parser.add_argument("username", type=str, help="El nombre de usuario")
    parser.add_argument("password", type=str, help="La contraseña para el usuario")
    
    args = parser.parse_args()
    create_user(args.username, args.password)
