from sqlalchemy import text

from app.db.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.models.menu_item import MenuItem
from app.models.restaurant import Restaurant


PASSWORD = "Password@123"


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.execute(text("PRAGMA foreign_keys=ON"))

    try:
        if db.query(User).first() is not None:
            print("Database already has data. Delete campusbite.db to re-seed")
            return

        hashed_pwd = hash_password(PASSWORD)

        # ----------- users ---------
        customers = [
            User(name="Aarav Shah", email="customer1@campusbite.com", hashed_password=hashed_pwd, role=UserRole.CUSTOMER, phone="+919000000001", address="Hostel A, Room 101"),
            User(name="Diya Patel", email="customer2@campusbite.com", hashed_password=hashed_pwd, role=UserRole.CUSTOMER, phone="+919000000002", address="Hostel B, Room 202"),
            User(name="Rohan Mehta", email="customer3@campusbite.com", hashed_password=hashed_pwd, role=UserRole.CUSTOMER, phone="+919000000003", address="Library Block, Room 5")
        ]

        owners = [
            User(name="Spice Garden Owner", email="owner1@campusbite.com", hashed_password=hashed_pwd, role=UserRole.OWNER, phone="+919100000001", address="Campus Main Road"),
            User(name="Pizza Corner Owner", email="owner2@campusbite.com", hashed_password=hashed_pwd, role=UserRole.OWNER, phone="+919100000002", address="Campus Food Court")
        ]

        delivery_partners = [
            User(name="Kabir Rider", email="delivery1@campusbite.com", hashed_password=hashed_pwd, role=UserRole.DELIVERY, phone="+919200000001"),
            User(name="Meera Rider", email="delivery2@campusbite.com", hashed_password=hashed_pwd, role=UserRole.DELIVERY, phone="+919200000002"),
            User(name="Sahil Rider", email="delivery3@campusbite.com", hashed_password=hashed_pwd, role=UserRole.DELIVERY, phone="+919200000003")
        ]

        db.add_all(customers + owners + delivery_partners)
        db.flush() # assigns ids withou commiting

        # ---------- restaurants ---------
        spice = Restaurant(
            owner_id=owners[0].id,
            name="Spice Garden",
            description="North Indian comfort food, made fresh daily.",
            cuisine="Indian",
            address="Campus Main Road"
        )

        pizza = Restaurant(
            owner_id=owners[1].id,
            name="Pizza Corner",
            description="Wood-fired style pizzas, pasta and sides.",
            cuisine="Italian",
            address="Campus Food Court"
        )

        db.add_all([spice, pizza])
        db.flush()

        # --------- menu items ----------
        spice_menu = [
            ("Paneer Butter Masala", "Creamy tomato gravy with paneer cubes", 180, "Main Course", True),
            ("Dal Tadka", "Yellow lentils with a garlic tempering", 120, "Main Course", True),
            ("Butter Naan", "Soft tandoor-baked bread", 35, "Breads", True),
            ("Veg Biryani", "Fragrant rice with mixed vegetables", 150, "Rice", True),
            ("Chicken Curry", "Home-style chicken gravy", 220, "Main Course", False),
            ("Masala Chai", "Spiced Indian tea", 20, "Beverages", True),
            ("Gulab Jamun", "Two pieces, served warm", 50, "Desserts", True),
            ("Samosa", "Crispy potato-filled pastry", 25, "Starters", True)
        ]

        pizza_menu = [
            ("Margherita Pizza", "Classic tomato and mozzarella", 199, "Pizza", True),
            ("Farmhouse Pizza", "Capsicum, onion, mushroom, tomato", 279, "Pizza", True),
            ("Peppy Paneer Pizza", "Paneer and red paprika", 299, "Pizza", True),
            ("White Sauce Pasta", "Penne in creamy white sauce", 169, "Pasta", True),
            ("Garlic Bread", "Toasted with garlic butter", 99, "Sides", True),
            ("Choco Lava Cake", "Warm cake with a molten centre", 89, "Desserts", False),
            ("Cold Coffee", "Chilled coffee with ice cream", 79, "Beverages", True)
        ]

        for restaurant, menu in ((spice, spice_menu), (pizza, pizza_menu)):
            for name, des, price, category, available in menu:
                db.add(MenuItem(
                    restaurant_id=restaurant.id,
                    name=name,
                    description=des,
                    price=price,
                    category=category,
                    is_available=available
                ))

        db.commit()
        print("Seed complete:")
        print(f"  {len(customers)} customers, {len(owners)} owners, {len(delivery_partners)} delivery partners")
        print("  2 restaurants, 15 menu items")
        print(f"  Password for every seeded account: {PASSWORD}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__=="__main__":
    seed()