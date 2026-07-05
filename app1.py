import streamlit as st
import pyodbc
import pandas as pd
import smtplib
from email.mime.text import MIMEText
import base64

# ---------------- BACKGROUND IMAGE ----------------
def set_background(image_file):
    with open(image_file, "rb") as f:
        data = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{data}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

set_background("mustang.jpg")   # 🔥 make sure image is in same folder

# ---------------- DB CONNECTION ----------------
try:
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost\\SQLEXPRESS;'
        'DATABASE=VehicleServiceDB;'
        'Trusted_Connection=yes;'
    )
    cursor = conn.cursor()
except Exception as e:
    st.error(f"Database Connection Failed: {e}")
    st.stop()

# ---------------- EMAIL FUNCTION ----------------
def send_email(to_email, message):
    sender_email = "Put You Mail"   # 🔴 change
    app_password = "Put your App Password"       # 🔴 change (no spaces)

    msg = MIMEText(message)
    msg['Subject'] = "🚗 Vehicle Ready for Pickup"
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        return str(e)

# ---------------- PAGE ----------------
st.set_page_config(page_title="Vehicle Service Center", layout="wide")
st.title("🚗 Vehicle Service Center Management System")

menu = st.radio(
    "Navigation",
    ["Add Record", "View Records", "Pending Payments", "Update Payment"]
)

# ---------------- SERVICE PRICE ----------------
services_dict = {
    "Bike": {
        "Oil Change": 800,
        "Water Washing": 200,
        "Basic Service": 1000,
        "Full Service": 2000
    },
    "Car": {
        "Oil Change": 1500,
        "Water Washing": 500,
        "Basic Service": 2000,
        "Full Service": 4000,
        "Engine Repair": 6000
    }
}

# ================= ADD RECORD =================
if menu == "Add Record":

    st.header("Add Service Record")

    if st.button("🔄 Reset Form"):
        for key in list(st.session_state.keys()):
            if isinstance(st.session_state[key], bool):
                st.session_state[key] = False
            else:
                st.session_state[key] = ""
        st.rerun()

    name = st.text_input("Customer Name", key="name")
    email = st.text_input("Customer Email", key="email")
    phone = st.text_input("Phone", key="phone")
    model = st.text_input("Vehicle Model", key="model")
    reg = st.text_input("Registration No", key="reg")

    vehicle_type = st.radio("Select Vehicle Type", ["Bike", "Car"])

    st.subheader("Select Services")

    selected_services = []
    total_cost = 0

    for service, price in services_dict[vehicle_type].items():
        if st.checkbox(f"{service} (₹{price})", key=service):
            selected_services.append(service)
            total_cost += price

    service_display = " + ".join(selected_services)

    st.write(f"**Selected Service:** {service_display}")
    st.write(f"**Total Cost:** ₹{total_cost}")

    discount = st.number_input("Discount (%)", 0, 100, 0)
    final_amount = total_cost - (total_cost * discount / 100)

    st.write(f"**Final Amount after Discount:** ₹{final_amount}")

    if st.button("Submit"):

        if not all([name, email, phone, model, reg]):
            st.error("All fields required!")

        elif len(selected_services) == 0:
            st.error("Select at least one service!")

        else:
            try:
                cursor.execute(
                    "INSERT INTO Customer (Name, Phone, Email) VALUES (?, ?, ?)",
                    (name, phone, email)
                )
                conn.commit()

                cursor.execute("SELECT TOP 1 Customer_ID FROM Customer ORDER BY Customer_ID DESC")
                cid = cursor.fetchone()[0]

                cursor.execute(
                    "INSERT INTO Vehicle (Customer_ID, Model, Registration_No) VALUES (?, ?, ?)",
                    (cid, model, reg)
                )
                conn.commit()

                cursor.execute("SELECT TOP 1 Vehicle_ID FROM Vehicle ORDER BY Vehicle_ID DESC")
                vid = cursor.fetchone()[0]

                cursor.execute("INSERT INTO Employee (Name, Role) VALUES ('Default', 'Mechanic')")
                conn.commit()

                cursor.execute("SELECT TOP 1 Employee_ID FROM Employee ORDER BY Employee_ID DESC")
                eid = cursor.fetchone()[0]

                cursor.execute(
                    """INSERT INTO Service 
                    (Vehicle_ID, Employee_ID, Service_Type, Service_Date, Cost) 
                    VALUES (?, ?, ?, GETDATE(), ?)""",
                    (vid, eid, service_display, float(final_amount))
                )
                conn.commit()

                cursor.execute("SELECT TOP 1 Service_ID FROM Service ORDER BY Service_ID DESC")
                sid = cursor.fetchone()[0]

                cursor.execute(
                    """INSERT INTO Billing 
                    (Service_ID, Total_Amount, Payment_Status) 
                    VALUES (?, ?, 'Pending')""",
                    (sid, float(final_amount))
                )
                conn.commit()

                st.success("✅ Record Added Successfully!")

            except Exception as e:
                st.error(f"Error: {e}")

# ================= VIEW RECORDS =================
elif menu == "View Records":

    st.header("All Records")

    df = pd.read_sql("""
    SELECT 
        c.Customer_ID,
        c.Name,
        c.Phone,
        c.Email,
        v.Model,
        v.Registration_No,
        s.Service_Type,
        s.Service_Date,
        b.Total_Amount,
        b.Payment_Status
    FROM Customer c
    JOIN Vehicle v ON c.Customer_ID = v.Customer_ID
    JOIN Service s ON v.Vehicle_ID = s.Vehicle_ID
    JOIN Billing b ON s.Service_ID = b.Service_ID
    """, conn)

    st.dataframe(df, use_container_width=True)

# ================= PENDING =================
elif menu == "Pending Payments":

    st.header("Pending Payments")

    df = pd.read_sql("""
    SELECT b.Bill_ID, c.Name, c.Email, v.Model, b.Total_Amount
    FROM Billing b
    JOIN Service s ON b.Service_ID = s.Service_ID
    JOIN Vehicle v ON s.Vehicle_ID = v.Vehicle_ID
    JOIN Customer c ON v.Customer_ID = c.Customer_ID
    WHERE b.Payment_Status = 'Pending'
    """, conn)

    for i, row in df.iterrows():

        st.write(f"**Bill ID:** {row['Bill_ID']}")
        st.write(f"Customer: {row['Name']}")
        st.write(f"Email: {row['Email']}")
        st.write(f"Vehicle: {row['Model']}")
        st.write(f"Amount: ₹{row['Total_Amount']}")

        if st.button(f"🚗 Ready - {row['Bill_ID']}"):

            message = f"""
Hello {row['Name']} 👋

🚗 Your vehicle ({row['Model']}) is READY for pickup!

💰 Amount: ₹{row['Total_Amount']}

Thank you 🙏
"""

            result = send_email(row['Email'], message)

            if result == True:
                st.success(f"📧 Email sent to {row['Email']}")
            else:
                st.error(f"Email Failed: {result}")

        st.markdown("---")

# ================= UPDATE =================
elif menu == "Update Payment":

    st.header("Update Payment")

    bill_id = st.text_input("Enter Bill ID")

    if st.button("Mark as Paid"):

        if not bill_id:
            st.error("Enter Bill ID!")

        else:
            cursor.execute(
                "UPDATE Billing SET Payment_Status='Completed' WHERE Bill_ID=?",
                (bill_id,)
            )
            conn.commit()

            st.success("✅ Payment Updated Successfully!")