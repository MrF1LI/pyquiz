from flask import Flask, render_template, url_for, redirect, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Sheet API

credentials = None

SCOPES = ['https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/drive.readonly',
          'https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/spreadsheets.readonly']

credentials = ServiceAccountCredentials.from_json_keyfile_name('creds.json', SCOPES)
client = gspread.authorize(credentials)
sheet = client.open('Final - Copy').sheet1
data = sheet.get_all_records()

# App Config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schedule.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'nobody'
db = SQLAlchemy(app)


# Database

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    schedule = db.Column(db.String(100), nullable=False)


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    step = db.Column(db.String(500))
    course = db.Column(db.String(500))
    format = db.Column(db.String(500))
    group = db.Column(db.String(500))
    lecturer = db.Column(db.String(500))
    time = db.Column(db.String(500))
    date = db.Column(db.String(500))
    semester = db.Column(db.String(500))


db.create_all()

# From api to db

for each in data:
    new_item = Schedule(step=each['საფეხური'],
                        course=each['სასწავლო კურსი'],
                        format=each['გამოცდის ფორმატი'],
                        group=each['ჯგუფის დასახელება'],
                        lecturer=each['ლექტორი'],
                        time=each['საგამოცდო დრო'],
                        date=each['საგამოცდო დღე'],
                        semester=each['სემესტრი'])
    exists = bool(
        Schedule.query.filter_by(step=new_item.step, course=new_item.course, format=new_item.format,
                                 lecturer=new_item.lecturer, group=new_item.group, semester=new_item.semester,
                                 time=new_item.time, date=new_item.date).first())

    if not exists:
        db.session.add(new_item)
        db.session.commit()


# Pages

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/authorization', methods=['GET', 'POST'])
def authorization():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if email and password:
            user = Users.query.filter_by(email=email).first()
            if user is not None:
                if user.password == password:
                    session['currentUserEmail'] = email
                    session['currentUserFirstname'] = user.firstname
                    session['currentUserLastname'] = user.lastname
                    return redirect(url_for('profile'))
                else:
                    flash('თქვენს მიერ შეყვანილი პაროლი არასწორია.')
            else:
                flash('ანგარიში ვერ მოიძებნა.')
        else:
            flash('გთხოვთ შეიყვანოთ ელ. ფოსტა და პაროლი.')

    return render_template('authorization.html')


@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        date = request.form['date']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        if firstname and lastname and date and email and password and confirm_password:
            if password == confirm_password:
                if Users.query.filter_by(email=email).first() is None:
                    user = Users(firstname=firstname, lastname=lastname, date=date, email=email, password=password, schedule="")
                    db.session.add(user)
                    db.session.commit()
                    session['currentUserEmail'] = email
                    session['currentUserFirstname'] = firstname
                    session['currentUserLastname'] = lastname
                    return redirect(url_for('profile'))
                else:
                    flash('ანგარიში ასეთი ელ. ფოსტით უკვე არსებობს')
            else:
                flash('პაროლის დადასტურება ვერ მოხერხდა.')
        else:
            flash('გთხოვთ შეავსოთ ყველა მონაცემია.')

    return render_template('registration.html')


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    current_user = Users.query.filter_by(email=session['currentUserEmail']).first()

    if request.method == 'GET':
        delete_item = request.args.get('delete_item')
        if delete_item:
            current_user.schedule = current_user.schedule.replace(f'{delete_item}', '')
            db.session.commit()

    if request.method == "POST":
        current_user.firstname = request.form['firstname']
        current_user.lastname = request.form['lastname']
        current_user.date = request.form['date']
        db.session.commit()
        flash('მონაცემები წარმატებით შეიცვალა.')
        return redirect(url_for('profile'))

    user_schedule = current_user.schedule.split()

    schedule_data = Schedule.query.filter(Schedule.id.in_(user_schedule)).all()

    return render_template('profile.html', current_user=current_user, data=schedule_data)


@app.route('/logout')
def logout():
    session.pop('currentUserEmail', None)
    session.pop('currentUserFirstname', None)
    session.pop('currentUserLastname', None)
    return redirect(url_for('authorization'))


#

def check_selects(query, step, group, e_format):
    if step == 'მაგისტრატურა' or step == 'ბაკალავრიატი':
        query = query.filter(Schedule.step.contains(step))

    try:
        int(group)
        query = query.filter(Schedule.group.contains(group))
    except:
        pass

    if e_format == 'პრეზენტაცია' or e_format == 'წერითი':
        query = query.filter(Schedule.format == e_format)

    return query


@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'POST':
        if 'currentUserEmail' in session:
            current_user = Users.query.filter_by(email=session['currentUserEmail']).first()
            item_id = request.form['item_id']
            check_item = current_user.schedule.split()
            if item_id not in check_item:
                if current_user.schedule is None:
                    current_user.schedule = str(item_id)
                else:
                    current_user.schedule = f"{current_user.schedule} {item_id}"
                db.session.commit()
        else:
            return redirect(url_for('authorization'))

    search_keyword = request.args.get('search')

    step = request.args.get('step')
    group = request.args.get('group')
    e_format = request.args.get('format')

    if search_keyword:
        result = Schedule.query.filter(
            or_(
                Schedule.lecturer.contains(search_keyword),
                Schedule.course.contains(search_keyword),
                Schedule.date.contains(search_keyword)
            )
        )
        result = check_selects(result, step, group, e_format)

        searched_data = {
            "search_keyword": search_keyword,
            "step": step,
            "format": e_format,
            "group": group
        }

        return render_template('schedule.html', data=result, searched_data=searched_data)

    schedule_data = Schedule.query
    schedule_data = check_selects(schedule_data, step, group, e_format)

    user_schedule = []

    if 'currentUserEmai' in session:
        current_user = Users.query.filter_by(email=session['currentUserEmail']).first()
        user_schedule = current_user.schedule.split()
        user_schedule = [int(i) for i in user_schedule]

    searched_data = {
        "step": step,
        "format": e_format,
        "group": group
    }

    return render_template('schedule.html', data=schedule_data, user_schedule=user_schedule, searched_data=searched_data)


# Run

if __name__ == '__main__':
    app.run(debug=True)
