import mysql.connector as pysql
from mysql.connector import Error
from tabulate import tabulate

host = "localhost"
root_user = "root"
root_password = "12345678"
database = "hospital_db"

def connect_root():                 # Connects to MySQL as root
    try:
        return pysql.connect(host=host, user=root_user, password=root_password)
    except Error as e:
        print("\033[1;31mCould not connect to MySQL server:\033[0m", e)
        exit()

def connect_db():                   # Tries to connect to Database
    try:
        return pysql.connect(host = host, user = root_user, password = root_password, database = database)
    except Error as e:
        print(f"\033[1;31mCould not connect to database {database}:\033[0m", e)
        exit()

def db_init():                      # Set-up database with tables
    root = connect_root()
    cur_root = root.cursor()
    try:
        print("\033[0;36mEnsuring database exists...\033[0m")
        cur_root.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`;")
        cur_root.execute(f"USE `{database}`;")
    except Error as e:
        print("\033[1;31mDatabase initialisation failed:\033[0m", e)
        root.close()
        exit()
    root.close()
    con = connect_db()
    cur = con.cursor()
    try:
        # USERS table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS USERS (
                uid INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(30) UNIQUE,
                password VARCHAR(255) NOT NULL,
                name VARCHAR(30) NOT NULL,
                role ENUM('admin','doctor','pharmacist','patient') NOT NULL,
                specialization VARCHAR(100) DEFAULT NULL );
        """)
        # PHARMACY table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pharmacy (
                med_id INT AUTO_INCREMENT PRIMARY KEY,
                med_name VARCHAR(255) NOT NULL,
                quantity INT NOT NULL DEFAULT 0,
                price DECIMAL(10,2) NOT NULL );
        """)
        # SALES_LOG table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales_log (
                sale_id INT AUTO_INCREMENT PRIMARY KEY,
                med_id INT NOT NULL,
                quantity_sold INT NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                sold_by INT,
                sold_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (med_id) REFERENCES pharmacy(med_id)
                    ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (sold_by) REFERENCES USERS(uid)
                    ON DELETE SET NULL ON UPDATE CASCADE );
        """)
        # PRESCRIPTIONS TABLE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prescriptions (
                prescription_id INT AUTO_INCREMENT PRIMARY KEY,
                doctor_uid INT NOT NULL,
                patient_uid INT NOT NULL,
                description TEXT NOT NULL,
                date_issued DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                patient_name VARCHAR(100),
                patient_age INT,
                patient_gender VARCHAR(20),
                patient_phone VARCHAR(30),
                disease VARCHAR(255),
                FOREIGN KEY (doctor_uid) REFERENCES USERS(uid)
                    ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (patient_uid) REFERENCES USERS(uid)
                    ON DELETE CASCADE ON UPDATE CASCADE);
        """)
        # BEDS table for maintaining beds
        cur.execute("""
            CREATE TABLE IF NOT EXISTS beds (
                bed_id INT AUTO_INCREMENT PRIMARY KEY,
                status ENUM('Available','Occupied') NOT NULL DEFAULT 'Available',
                patient_uid INT DEFAULT NULL,
                FOREIGN KEY (patient_uid) REFERENCES USERS(uid)
                    ON DELETE SET NULL ON UPDATE CASCADE );
        """)
        con.commit()

        # Ensure at least one admin exists, else create one
        cur_admin = con.cursor(dictionary=True)
        try:
            cur_admin.execute("SELECT COUNT(*) AS cnt FROM USERS WHERE role='admin';")
            r = cur_admin.fetchone()
            cnt = r['cnt'] if r else 0
            if cnt == 0:
                try:
                    cur_admin.execute(
                        "INSERT INTO USERS (username, password, name, role, specialization) VALUES (%s, %s, %s, %s, %s)",
                        ("superuser000", "admin123457", "default_admin_0", "admin", None))
                    con.commit()
                    print("\033[1;32mDefault admin 'superuser000' created (password 'admin123457').\033[0m")
                except Error as e:
                    print("\033[1;31mCould not create default admin:\033[0m", e)
        finally:
            cur_admin.close()
        print("\033[1;32mDatabase initialization complete.\033[0m")
    except Error as e:
        print("\033[1;31mInitialization SQL error:\033[0m", e)
    finally:
        cur.close()
        con.close()

def login():                            #Login function for authenticating users
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        print("\033[0;36m=== LOGIN ===\033[0m")
        username = input("Username: ")
        password = input("Password: ")
        cur.execute("SELECT * FROM USERS WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        if user:
            print(f"\033[1;32mLogged in as {user['name']},{user['role']}\033[0m")
            return user
        else:
            print("\033[1;31mInvalid credentials.\033[0m")
            return None
    except Error as e:
        print("\033[1;31mLogin error:\033[0m", e)
        return None
    finally:
        cur.close()
        con.close()

def change_password_user(uid):                  #Change user account password
    con = connect_db()
    cur1 = con.cursor(dictionary=True)
    try:
        print("\033[0;36mCHANGE PASSWORD\033[0m")
        old = input("Current password: ")
        cur1.execute("SELECT password FROM USERS WHERE uid=%s", (uid,))
        row = cur1.fetchone()
        if not row:
            print("\033[1;31mUser not found.\033[0m")
            return
        db_pass = row['password']
        if old != db_pass:
            print("\033[1;31mCurrent password incorrect.\033[0m")
            return
        new = input("New password: ")
        confirm = input("Confirm new password: ")
        if new != confirm:
            print("\033[1;31mPasswords do not match.\033[0m")
            return
        try:
            cur1.execute("UPDATE USERS SET password=%s WHERE uid=%s", (new, uid))
            con.commit()
            print("\033[1;32mPassword changed successfully.\033[0m")
        except Error as e:
            print("\033[1;31mFailed to change password:\033[0m", e)
    finally:
        cur1.close()
        con.close()

def admin_create_employee():                    #Creates entry for doctor or pharmacist
    con = connect_db()
    cur = con.cursor()
    try:
        print("\033[0;36mCreate new employee (doctor or pharmacist)\033[0m")
        name = input("Name: ")
        username = input("Username: ")
        password = input("Password: ")
        while True:
            ch = input("Role (1. doctor/ 2. pharmacist): ")
            if ch not in ("1", "2"):
                print("\033[1;31mChoose 1 or 2: \033[0m")
                continue
            else:
                role = "doctor" if ch == "1" else "pharmacist"
            break
        specialization = None
        if role == 'doctor':
            spec_list = ["General Medicine", "Cardiology", "Neurology", "Orthopedics", "Pediatrics",
                         "Dermatology", "ENT", "Gynecology", "Nephrology"]
            for i in range(1, len(spec_list) + 1):
                print(f"{i}. {spec_list[i - 1]}")               #Prints as <1. spec>
            try:
                ch = int(input("Choose: "))
                if 1 <= ch <= len(spec_list):
                    specialization = spec_list[ch - 1]
                else:
                    specialization = None
            except ValueError:
                specialization = None
        try:
            cur.execute(
                "INSERT INTO USERS (username, password, name, role, specialization) VALUES (%s,%s,%s,%s,%s)",
                (username, password, name, role, specialization))
            con.commit()
            print(f"\033[1;32mEmployee created with uid {cur.lastrowid}\033[0m")
        except Error as e:
            con.rollback()
            print("\033[1;31mCould not create employee:\033[0m", e)
    finally:
        cur.close()
        con.close()

def admin_remove_employee(user):                        #Can remove doctor or pharmacist
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        print("\033[0;36mRemove employee:\033[0m")
        try:
            uid = int(input("Enter employee uid to remove: "))
        except ValueError:
            print("\033[1;31mInvalid uid.\033[0m")
            return
        if uid == 1:
            print("\033[1;31mCannot remove default admin uid 1.\033[0m")
            return
        cur.execute("SELECT * FROM USERS WHERE uid=%s", (uid,))
        row = cur.fetchone()
        if not row:
            print("\033[1;31mNot found.\033[0m")
            return
        role = row['role']
        if role == 'admin':
            print("\033[1;31mAdmins cannot remove other admins.\033[0m")
            return
        print(f"\033[1;33mYou are about to REMOVE '{row['username']}' (role={row['role']}).\033[0m")
        confirm = input("Are you sure? (yes/no): ")
        if confirm != "yes":
            print("\033[1;31mRemoval cancelled.\033[0m")
            return
        admin_pass = input("Enter your admin password to confirm: ")
        cur.execute("SELECT password FROM USERS WHERE uid=%s", (user['uid'],))
        row2 = cur.fetchone()
        if not row2 or admin_pass != row2['password']:
            print("\033[1;31mPassword incorrect. Cannot proceed.\033[0m")
            return
        try:
            cur.execute("DELETE FROM USERS WHERE uid=%s", (uid,))
            con.commit()
            print("\033[1;32mEmployee removed successfully.\033[0m")
        except Error as e:
            print("\033[1;31mRemove failed:\033[0m", e)
    finally:
        cur.close()
        con.close()

def admin_modify_stock():                               #Enter records of new med or update them
    con = connect_db()
    cur = con.cursor()
    try:
        print("\033[0;36mModify stock (add new med or update existing)\033[0m")
        print("1. New")
        print("2. Update")
        ch = input("\033[1;33mChoice: \033[0m")
        if ch == '1':
            name = input("Medicine name: ")
            try:
                qty = int(input("Quantity (integer): "))
                price = float(input("Price per unit: "))
            except ValueError:
                print("\033[1;31mInvalid numeric input.\033[0m")
                return
            try:
                cur2 = con.cursor()
                cur2.execute("INSERT INTO pharmacy (med_name, quantity, price) VALUES (%s,%s,%s)",
                             (name, qty, price))
                con.commit()
                cur2.close()
                print("\033[1;32mMedicine added.\033[0m")
            except Error as e:
                con.rollback()
                print("\033[1;31mInsert failed:\033[0m", e)
        elif ch == '2':
            try:
                mid = int(input("med_id: "))
                cur.execute("SELECT * FROM pharmacy WHERE med_id=%s", (mid,))
                med = cur.fetchone()
                if not med:
                    print("\033[1;31mMedicine not found.\033[0m")
                    return
                print("Current:", med)
                qty = input("New quantity (leave blank to skip): ")
                if qty != "":
                    try:
                        qv = int(qty)
                        cur.execute("UPDATE pharmacy SET quantity=%s WHERE med_id=%s", (qv, mid))
                    except ValueError:
                        print("\033[1;31mInvalid quantity.\033[0m")
                        return
                price = input("New price (leave blank to skip): ")
                if price != "":
                    try:
                        pv = float(price)
                        cur.execute("UPDATE pharmacy SET price=%s WHERE med_id=%s", (pv, mid))
                    except ValueError:
                        print("\033[1;31mInvalid price.\033[0m")
                        return
                con.commit()
                print("\033[1;32mUpdate successful.\033[0m")
            except ValueError:
                print("\033[1;31mInvalid med_id.\033[0m")
        else:
            print("\033[1;31mInvalid option.\033[0m")
    finally:
        cur.close()
        con.close()

def admin_view_stock():                                 #View available medicine stock
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM pharmacy ORDER BY med_name")
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
        return
    if not rows:
        print("\033[0;33mNo medicines found.\033[0m")
        return
    print(tabulate(rows, headers="keys", tablefmt="grid"))

def admin_view_sales_log():                         #View previous sale records
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("""
            SELECT s.sale_id, p.med_name, s.quantity_sold, s.total_price, u.name AS sold_by, s.sold_at
            FROM sales_log s, pharmacy p, users u
            where s.sold_by = u.uid
            AND s.med_id = p.med_id
            ORDER BY s.sold_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
        return
    if not rows:
        print("\033[0;33mNo sales recorded.\033[0m")
        return
    print(tabulate(rows, headers="keys", tablefmt="grid"))

def admin_add_bed():                                    #Add new beds
    con = connect_db()
    cur = con.cursor()
    try:
        count = input("How many beds to add (integer): ")
        try:
            count = int(count)
        except ValueError:
            print("\033[1;31mInvalid integer.\033[0m")
            return
        try:
            for i in range(count):
                cur.execute("INSERT INTO beds (status, patient_uid) VALUES ('Available', NULL)")
            con.commit()
            print(f"\033[1;32mAdded {count} beds.\033[0m")
        except Error as e:
            print("\033[1;31mOperation Failed! Reason:\033[0m", e)
    finally:
        cur.close()
        con.close()

def admin_remove_bed():                                 #Remove bed
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        try:
            bed_id = int(input("Enter bed_id to remove: "))
        except ValueError:
            print("\033[1;31mInvalid bed_id.\033[0m")
            return
        cur.execute("SELECT * FROM beds WHERE bed_id=%s", (bed_id,))
        b = cur.fetchone()
        if not b:
            print("\033[1;31mBed not found.\033[0m")
            return
        status = b['status']
        if status != 'Available':
            print("\033[1;31mCannot remove occupied bed.\033[0m")
            return
        try:
            cur.execute("DELETE FROM beds WHERE bed_id=%s", (bed_id,))
            con.commit()
            print("\033[1;32mBed removed.\033[0m")
        except Error as e:
            print("\033[1;31mRemove failed:\033[0m", e)
    finally:
        cur.close()
        con.close()

def admin_view_beds():                                   #View current bed status
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM beds ORDER BY bed_id")
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
        return
    if not rows:
        print("\033[0;33mNo beds in system.\033[0m")
        return
    print(tabulate(rows, headers="keys", tablefmt="grid"))


def admin_view_all_prescriptions():                     #View all prescriptions in system
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("""
            SELECT pr.prescription_id as p_id,
                    u_doctor.name AS doc,
                    u_patient.name AS patient,
                    u_patient.uid as pat_uid,
                    pr.description,
                    pr.date_issued as DATE
            FROM prescriptions pr, USERS u_doctor, USERS u_patient
            WHERE pr.doctor_uid = u_doctor.uid
            AND pr.patient_uid = u_patient.uid
            ORDER BY pr.date_issued DESC;
        """)
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
        return
    if not rows:
        print("\033[0;33mNo prescriptions found.\033[0m")
        return
    print(tabulate(rows, headers="keys", tablefmt="grid"))


def doctor_view_patients():                             #View patient list
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT uid, name FROM USERS WHERE role='patient' ORDER BY name")
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
        return
    if not rows:
        print("\033[0;33mNo patients found.\033[0m")
        return
    print(tabulate(rows, headers="keys", tablefmt="grid"))


def doctor_create_prescription(user):                   #Create prescription
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        try:
            patient_uid = int(input("Patient uid: "))
        except ValueError:
            print("\033[1;31mInvalid patient uid.\033[0m")
            return
        cur.execute("SELECT * FROM USERS WHERE uid=%s AND role='patient'", (patient_uid,))
        row = cur.fetchone()
        if not row:
            print("\033[1;31mPatient not found.\033[0m")
            return
        else:
            print(f"\033[1;32mPatient found: {row['name']}, uid: {row['uid']}\033[0m")
        print("Enter prescription text. End with a blank line.")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        text = "\n".join(lines)
        if not text:
            print("\033[1;31mPrescription cannot be empty.\033[0m")
            return
        try:
            patient_name = input("Patient name: ")
            try:
                patient_age = int(input("Patient age: "))
            except ValueError:
                patient_age = None
            patient_gender = input("Patient gender: ")
            patient_phone = input("Patient phone: ")
            disease = input("Disease / Diagnosis: ")
            cur.execute(
                """
                INSERT INTO prescriptions
                (doctor_uid, patient_uid, description, date_issued,
                 patient_name, patient_age, patient_gender, patient_phone, disease)
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s)
                """,
                (user["uid"], patient_uid, text, patient_name, patient_age, patient_gender, patient_phone, disease)
            )
            con.commit()
            print(f"\033[1;32mPrescription created (id {cur.lastrowid}).\033[0m")
        except Error as e:
            print("\033[1;31mInsert failed:\033[0m", e)
    finally:
        cur.close()
        con.close()


def doctor_view_patient_prescriptions():                #View specific patient prescription
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        try:
            patient_uid = int(input("Patient uid to view: "))
        except ValueError:
            print("\033[1;31mInvalid uid.\033[0m")
            return
        cur.execute("""
            SELECT p.prescription_id,
                    u_doctor.name AS doctor,
                    p.description,
                    p.date_issued
            FROM prescriptions p,
            USERS u_doctor
            WHERE p.doctor_uid = u_doctor.uid
            AND p.patient_uid = %s
            ORDER BY p.date_issued DESC;""", (patient_uid,))
        rows = cur.fetchall()
        if not rows:
            print("\033[0;33mNo prescriptions for this patient.\033[0m")
            return
        print(tabulate(rows, headers="keys", tablefmt="grid"))
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
    finally:
        cur.close()
        con.close()


def doctor_assign_bed():                                #Assign bed to patient if needed
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        try:
            patient_uid = int(input("Patient uid to assign bed: "))
        except ValueError:
            print("\033[1;31mInvalid uid.\033[0m")
            return
        cur.execute("SELECT * FROM USERS WHERE uid=%s AND role='patient'", (patient_uid,))
        if not cur.fetchone():
            print("\033[1;31mPatient not found.\033[0m")
            return
        cur.execute(
            "SELECT * FROM beds WHERE patient_uid=%s AND status='Occupied'",
            (patient_uid,)
        )
        existing = cur.fetchone()
        if existing:
            print(f"\033[1;31mPatient already occupies bed {existing['bed_id']}.\033[0m")
            return
        cur.execute("SELECT * FROM beds WHERE status='Available' LIMIT 1")
        bed = cur.fetchone()
        if not bed:
            print("\033[1;31mNo available beds.\033[0m")
            return
        try:
            cur.execute("UPDATE beds SET status='Occupied', patient_uid=%s WHERE bed_id=%s",
                        (patient_uid, bed['bed_id']))
            con.commit()
            print(f"\033[1;32mAssigned bed {bed['bed_id']} to patient {patient_uid}.\033[0m")
        except Error as e:
            print("\033[1;31mAssign failed:\033[0m", e)
    finally:
        cur.close()
        con.close()


def doctor_release_bed():                           #Discharge patient, release bed
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        try:
            patient_uid = int(input("Patient uid to discharge (release bed): "))
        except ValueError:
            print("\033[1;31mInvalid uid.\033[0m")
            return
        cur.execute("SELECT * FROM beds WHERE patient_uid=%s AND status='Occupied' LIMIT 1", (patient_uid,))
        bed = cur.fetchone()
        if not bed:
            print("\033[0;33mNo bed assigned to this patient.\033[0m")
            return
        try:
            cur.execute("UPDATE beds SET status='Available', patient_uid=NULL WHERE bed_id=%s", (bed['bed_id'],))
            con.commit()
            print(f"\033[1;32mBed {bed['bed_id']} released.\033[0m")
        except Error as e:
            con.rollback()
            print("\033[1;31mRelease failed:\033[0m", e)
    finally:
        cur.close()
        con.close()


def pharmacist_view_stock():                    #View medicine stock
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM pharmacy ORDER BY med_id")
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
        return
    if not rows:
        print("\033[0;33mNo stock found.\033[0m")
        return
    print(tabulate(rows, headers="keys", tablefmt="grid"))


def pharmacist_update_stock():              #Update Available stock
    con = connect_db()
    cur = con.cursor()
    try:
        try:
            med_id = int(input("med_id to update: "))
        except ValueError:
            print("\033[1;31mInvalid med_id.\033[0m")
            return
        cur.execute("SELECT * FROM pharmacy WHERE med_id=%s", (med_id,))
        med = cur.fetchone()
        if not med:
            print("\033[1;31mMedicine not found.\033[0m")
            return
        try:
            qty = int(input("New quantity (integer): "))
        except ValueError:
            print("\033[1;31mInvalid quantity.\033[0m")
            return
        try:
            price = float(input("New price (float): "))
        except ValueError:
            print("\033[1;31mInvalid price.\033[0m")
            return
        try:
            cur.execute("UPDATE pharmacy SET quantity=%s, price=%s WHERE med_id=%s", (qty, price, med_id))
            con.commit()
            print("\033[1;32mStock updated.\033[0m")
        except Error as e:
            con.rollback()
            print("\033[1;31mUpdate failed:\033[0m", e)
    finally:
        cur.close()
        con.close()


def pharmacist_sell_cart(user):             #Sale and billing - pharmacy
    con = connect_db()
    cur = con.cursor(dictionary=True)
    cart = []
    try:
        while True:
            med_input = input("Enter med_id to add to cart (or blank to checkout): ")
            if med_input == "":
                confirm = input("Confirm checkout? (y/n): ")
                if confirm in "Yy":
                    break
                else:
                    continue
            try:
                med_id = int(med_input)
            except ValueError:
                print("\033[1;31mInvalid med_id.\033[0m")
                continue
            cur.execute("SELECT * FROM pharmacy WHERE med_id=%s", (med_id,))
            med = cur.fetchone()
            if not med:
                print("\033[1;31mMedicine not found.\033[0m")
                continue
            print("Selected:", med)
            try:
                qty = int(input("Quantity: "))
            except ValueError:
                print("\033[1;31mInvalid quantity.\033[0m")
                continue
            if qty <= 0:
                print("\033[1;31mQuantity must be > 0.\033[0m")
                continue
            available = med['quantity']
            unit_price = float(med['price'])
            med_name = med['med_name']
            if qty > available:
                print(f"\033[1;31mInsufficient stock (available {available}).\033[0m")
                continue
            cart.append((med_id, med_name, qty, unit_price))
            print("\033[1;32mAdded to cart.\033[0m")
        if not cart:
            print("\033[0;33mCart empty.\033[0m")
            return

        print("\033[0;36m=== BILL ===\033[0m")
        table = []
        total = 0
        for med_id, name, qty, price in cart:
            item_total = qty * price
            total += item_total
            table.append([med_id, name, qty, price, item_total])
        print(tabulate(
            table,
            headers=["Med ID", "Name", "Qty", "Unit Price", "Item Total"],
            tablefmt="grid"
        ))

        print(f"\033[1;33mTOTAL:\033[0m {total}")
        confirm = input("Proceed to billing? (y/n): ")
        if confirm not in "Yy":
            print("\033[0;33mCheckout cancelled.\033[0m")
            return
        try:
            for med_id, mname, qty, price in cart:
                line_total = qty * price
                cur2 = con.cursor()
                cur2.execute(
                    "INSERT INTO sales_log (med_id, quantity_sold, total_price, sold_by) "
                    "VALUES (%s, %s, %s, %s)",
                    (med_id, qty, line_total, user['uid'])
                )
                cur2.execute(
                    "UPDATE pharmacy SET quantity = quantity - %s WHERE med_id=%s",
                    (qty, med_id)
                )
                cur2.close()
            con.commit()
            print(f"\033[1;32mCheckout successful. Total: {total}\033[0m")
        except Error as e:
            print("\033[1;31mCheckout failed:\033[0m", e)
    finally:
        cur.close()
        con.close()

def pharmacist_view_sales_log():            #View all previous sales
    try:
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("""
            SELECT s.sale_id, p.med_name, s.quantity_sold, s.total_price, u.name AS sold_by, s.sold_at 
            FROM sales_log s, pharmacy p, USERS u
            WHERE s.med_id = p.med_id
            AND s.sold_by = u.uid
            ORDER BY s.sold_at DESC;
        """)
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
        return
    if not rows:
        print("\033[0;33mNo sales recorded.\033[0m")
        return
    print(tabulate(rows, headers="keys", tablefmt="grid"))

def register_as_patient():                  #Create patient user account
    print("\033[0;36m=== PATIENT REGISTRATION ===\033[0m")
    con = None
    cur = None
    try:
        name = input("Name: ")
        username = input("Choose a username: ")
        password = input("Choose a password: ")
        if username == "" or password == "":
            print("\033[1;31mFields cannot be empty.\033[0m")
            return
        con = connect_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM USERS WHERE username = %s", (username,))
        if cur.fetchone():
            print("\033[1;31mUsername already exists.\033[0m")
            return
        cur.execute("""
            INSERT INTO USERS (username, password, name, role, specialization)
            VALUES (%s, %s, %s, 'patient', NULL)
        """, (username, password, name))
        con.commit()
        print("\033[1;32mPatient registered successfully.\033[0m")
    except Error as e:
        print("\033[1;31mError registering patient:\033[0m", e)
    finally:
       cur.close()
       con.close()

def patient_view_prescriptions(user):       #View own prescriptions
    con = connect_db()
    cur = con.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT p.prescription_id, u_doctor.name AS doctor, p.description, p.date_issued
                FROM prescriptions p, USERS u_doctor
                WHERE p.doctor_uid = u_doctor.uid
                AND p.patient_uid = %s
                ORDER BY p.date_issued DESC
        """, (user['uid'],))
        rows = cur.fetchall()
        if not rows:
            print("\033[0;33mNo prescriptions found.\033[0m")
            return
        print(tabulate(rows, headers="keys", tablefmt="grid"))
    except Error as e:
        print("\033[1;31mDB error:\033[0m", e)
    finally:
        cur.close()
        con.close()


#MENUS
def admin_menu(user):
    while True:
        print("\033[0;36m=== ADMIN MENU ===\033[0m")
        print("1. Create employee (doctor/pharmacist)")
        print("2. Remove employee")
        print("3. Modify pharmacy stock (add/update)")
        print("4. View pharmacy stock")
        print("5. View sales log")
        print("6. Add beds")
        print("7. Remove bed")
        print("8. View beds")
        print("9. View all prescriptions")
        print("10. Change account password")
        print("0. Logout")
        choice = input("Choice: ")
        if choice == "1":
            admin_create_employee()
        elif choice == "2":
            admin_remove_employee(user)
        elif choice == "3":
            admin_modify_stock()
        elif choice == "4":
            admin_view_stock()
        elif choice == "5":
            admin_view_sales_log()
        elif choice == "6":
            admin_add_bed()
        elif choice == "7":
            admin_remove_bed()
        elif choice == "8":
            admin_view_beds()
        elif choice == "9":
            admin_view_all_prescriptions()
        elif choice == "10":
            change_password_user(user["uid"])
        elif choice == "0":
            break
        else:
            print("\033[1;31mInvalid option.\033[0m")

def doctor_menu(user):
    while True:
        print("\033[0;36m=== DOCTOR MENU ===\033[0m")
        print("1. View patient list")
        print("2. Create prescription")
        print("3. View past prescriptions for a patient")
        print("4. Assign bed to patient")
        print("5. Release bed (discharge)")
        print("6. Change account password")
        print("0. Logout")
        choice = input("Choice: ")
        if choice == "1":
            doctor_view_patients()
        elif choice == "2":
            doctor_create_prescription(user)
        elif choice == "3":
            doctor_view_patient_prescriptions()
        elif choice == "4":
            doctor_assign_bed()
        elif choice == "5":
            doctor_release_bed()
        elif choice == "6":
            change_password_user(user["uid"])
        elif choice == "0":
            break
        else:
            print("\033[1;31mInvalid option.\033[0m")

def pharmacist_menu(user):
    while True:
        print("\033[0;36m=== PHARMACIST MENU ===\033[0m")
        print("1. View stock")
        print("2. Update stock")
        print("3. Sell")
        print("4. View sales log")
        print("5. Change account password")
        print("0. Logout")
        choice = input("Choice: ")
        if choice == "1":
            pharmacist_view_stock()
        elif choice == "2":
            pharmacist_update_stock()
        elif choice == "3":
            pharmacist_sell_cart(user)
        elif choice == "4":
            pharmacist_view_sales_log()
        elif choice == "5":
            change_password_user(user["uid"])
        elif choice == "0":
            break
        else:
            print("\033[1;31mInvalid option.\033[0m")

def patient_menu(user):
    while True:
        print("\033[0;36m=== PATIENT MENU ===\033[0m")
        print("1. View my prescriptions")
        print("2. Change account password")
        print("0. Logout")
        choice = input("Choice: ")
        if choice == "1":
            patient_view_prescriptions(user)
        elif choice == "2":
            change_password_user(user["uid"])
        elif choice == "0":
            break
        else:
            print("\033[1;31mInvalid option.\033[0m")

def menu():
    db_init()
    print("\033[1;32mWelcome to the Hospital-Management-System (v1.0)\033[0m")
    while True:
        print("\033[0;36m=== MENU ===\033[0m")
        print("1. Login")
        print("2. Register as Patient")
        print("3. Exit")
        choice = input("Choice: ")
        if choice == "1":
            user = login()
            if not user:
                continue
            role = user['role']
            if role == 'admin':
                admin_menu(user)
            elif role == 'doctor':
                doctor_menu(user)
            elif role == 'pharmacist':
                pharmacist_menu(user)
            elif role == 'patient':
                patient_menu(user)
            else:
                print("\033[1;31mUnknown role.\033[0m")
        elif choice == "2":
            register_as_patient()
        elif choice == "3":
            print("\033[0;36mExiting...\033[0m")
            break
        else:
            print("\033[1;31mInvalid option.\033[0m")

#RUN PROGRAM
menu()
