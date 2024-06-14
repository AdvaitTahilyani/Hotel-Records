import csv
import os
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import requests
import urllib.parse
import names


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///data.db")
def load():
    db.execute("DELETE FROM info;")
    db.execute("DELETE FROM link;")
    with open('hotel_customer_profile.csv', newline='') as csvfile:
        profile = csv.reader(csvfile, delimiter=',')
        for row in profile:
            if row[0] == 'customer_id':
                continue
            if row[8] == 'Male':
                row.append(names.get_full_name(gender='male'))
            else:
                row.append(names.get_full_name(gender='female'))
            if row[1] == '0':
                row[1] = 'Married'
            else:
                row[1] = 'Unmarried'
            put(row,-1,1)

def calc(income, bill, visits, purpose):
    score = 0
    if purpose == "Business Travel":
        score+=2
    else:
        score+=1
    if bill > 10000.0 and bill <= 30000.0:
        score+=1
    elif bill > 30000.0 and bill <= 50000.0:
        score+=2
    elif bill > 50000.0 and bill <= 100000.0:
        score+=3
    elif bill > 100000.0 and bill <= 200000.0:
        score+=4
    elif bill > 200000.0:
        score+=5
    if visits >8.0:
        score+=5
    elif visits >6.0 and visits <=8.0:
        score+=4
    elif visits >4.0 and visits <=6.0:
        score+=3
    elif visits >2.0 and visits <=4.0:
        score+=2
    elif visits >0.0 and visits <=2.0:
        score+=1
    if income == "225,000-250,000" or income == "250,000-300,000" or income == "300,000-500,000":
        score+=1
    elif income == "500,000-700,000" or income == "700,000-1,000,000":
        score+=2
    elif income == "1,000,000-1,500,000" or income == "1,500,000-2,000,000":
        score+=3
    elif income == "2,000,000-2,500,000":
        score+=4
    elif income == "2,500,000+":
        score+=5
    return score
def put(row, user, type):
    for i in range(15):
        row[i] = str(row[i]).strip()
    score = calc(str(row[4]), float(row[5]), int(row[11]), str(row[10]))
    if score > 10:
        row[13] = "HVC"
        gift = "$150"
    elif score > 7:
        row[13] = "MVC"
        gift = "$75"
    else:
        row[13] = "LVC"
        gift = "$0"
    db.execute("INSERT INTO Info(id,Marital_Status,Age,Age_bucket,Income_Range,Bill_amount,Communication_method,Payment_Method,Gender,Transactions,Travel_purpose,Visits,Room_type,Value,Score,Name,Gift) VALUES(:id,:Marital_Status,:Age,:Age_bucket,:Income_Range,:Bill_amount,:Communication_method,:Payment_Method,:Gender,:Transactions,:Travel_purpose,:Visits,:Room_type,:Value,:Score,:name,:gift);",id = int(row[0]),Marital_Status = row[1], Age = int(row[2]), Age_bucket = row[3], Income_Range = row[4], Bill_amount = float(row[5]), Communication_method = row[6], Payment_Method = row[7], Gender = row[8], Transactions = int(row[9]), Travel_purpose = row[10], Visits = int(row[11]), Room_type = row[12], Value = row[13], name = row[14], Score = score, gift = gift)
    db.execute("INSERT INTO link(customer, user, type) VALUES(:customer,:user, :type);", customer = row[0], user = user, type = type)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function
@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        duplicate = db.execute("SELECT * FROM users WHERE username = :username",username=request.form.get("username"))
        if len(duplicate)!= 0:
            return apology("this username exists", 403)
        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password", 403)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)
        hash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username,hash) VALUES (:username, :hash);", username = request.form.get("username"), hash = hash)
        return redirect("/")
    else:
        return render_template("register.html")
@app.route("/")
@login_required
def index():
    row = db.execute("SELECT * FROM Info JOIN link ON Info.id = link.customer WHERE link.user = :user GROUP BY Info.id ORDER BY link.id DESC LIMIT 10;", user = int(session.get('user_id')))
    return render_template("index.html", table = row, length = len(row))
@app.route("/insert", methods=["GET", "POST"])
@login_required
def insert():
    if request.method == 'POST':
        name = ['Marital_Status','Age','Age_bucket','Income_Range','Bill_amount','Communication_method','Payment_Method','Gender','Transactions_made','Travel_purpose','Visits','Room_type','Name']
        id1 = db.execute("SELECT id FROM Info ORDER BY id DESC LIMIT 1")
        id = id1[0]['id']
        id = int(id)+1
        row = [id]
        for i in name:
            if i == 'Age_bucket':
                n = int(request.form.get(name[1]))
                if n > 60:
                    row.append('Above 60')
                    continue
                elif n < 20:
                    row.append('Below 20')
                    continue
                elif n % 10 == 0:
                    n-=10
                n = n//10
                n*=10
                n+=1
                cpy = str(n)
                cpy+='-'
                cpy+=str(n+9)
                row.append(cpy)
                continue
            if i == 'Name':
                row.append('HVC')
            row.append(request.form.get(i))
        put(row, session.get('user_id'), 1)
        return redirect("/")
    else:
        list = [['Name', 'Name'], ['Age', 'Age'], ['Bill_amount', 'Bill Amount'], ['Transactions_made', 'Transactions Made'], ['Visits', 'Visits']]
        search = ['Marital_Status', 'Income_Range', 'Communication_method', 'Payment_Method', 'Gender', 'Travel_purpose', 'Room_type']
        look = []
        for i in search:
            look.append(i.replace("_", " "))
        row = []
        for i in search:
            row.append(db.execute("SELECT " + i + " FROM Info GROUP BY " + i + ";"))
        return render_template("insert.html", list = list, check = row, search = search, look = look)
@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if request.method == 'POST':
        row = db.execute("SELECT * FROM Info WHERE Name LIKE :name;", name = '%' + request.form.get("name") + '%')
        for i in row:
            db.execute("INSERT INTO link(customer,user,type) VALUES(:customer, :user, :type);", customer = i['id'], user = session.get('user_id'), type = 0)
        print(row)
        return render_template("searched.html", table = row)
    else:
        return render_template("search.html")
@app.route("/advance", methods=["GET", "POST"])
@login_required
def advance():
    if request.method == 'POST':
        search = ['Marital_Status', 'Income_Range', 'Communication_method', 'Payment_Method', 'Gender', 'Travel_purpose', 'Room_type', 'Age_bucket']
        row = []
        for i in search:
            row.append(db.execute("SELECT " + i + " FROM Info GROUP BY " + i + ";"))
        flag = 0
        empty = 0
        st = "SELECT * FROM Info WHERE "
        for i in range(8):
            flag1 = 0
            did = 0
            for j in row[i]:
                temp = request.form.get(str(j[search[i]]))
                if temp != None:
                    empty = 1
                    did = 1
                    temp = temp.strip()
                    if flag == 0:
                        st+= "(" + search[i] + "='" + temp + "' "
                        flag = 1
                        flag1 = 1
                    else:
                        if flag1 == 0:
                            st+= "AND " + "(" + search[i] + "='" + temp + "' "
                            flag1 = 1
                        else:
                            st+= "OR " + search[i] + "='" + temp + "' "
            if did == 1:
                st+=")"
        st = st.strip()
        st+=";"
        if empty == 1:
            final = db.execute(st)
            return render_template("advanced.html", table = final, number = len(final))
        else:
            return apology("Kindly tick a box")
    else:
        search = ['Marital_Status', 'Income_Range', 'Communication_method', 'Payment_Method', 'Gender', 'Travel_purpose', 'Room_type', 'Age_bucket']
        look = []
        for i in search:
            look.append(i.replace("_", " "))
        row = []
        for i in search:
            row.append(db.execute("SELECT " + i + " FROM Info GROUP BY " + i + ";"))
        return render_template("advance.html", check = row, search = search, look = look)
@app.route("/about")
@login_required
def about():
    return render_template("about.html")
@app.route("/loaded", methods=["GET", "POST"])
@login_required
def loaded():
    if request.method == "POST":
        load()
        return redirect("/")
    else:
        return render_template("load.html")
def apology(message, code=400):
    def escape(s):
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code
def errorhandler(e):
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)