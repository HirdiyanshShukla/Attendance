from django.shortcuts import render
from django.conf import settings

import requests
from bs4 import BeautifulSoup
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def home(request):
    context = {}

    try:
        # STEP 1: Set up login
        login_url = "https://campus.srmcem.ac.in/psp/ps/?&cmd=login&languageCd=UKE"
        u_id = settings.CLG_USERNAME
        password = settings.CLG_PASSWORD

        payload = {
            'cmd': 'login',
            'languageCd': 'UKE',
            'timezoneOffset': '0',
            'userid': u_id,
            'pwd': password,
            'Submit': 'Sign In'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://campus.srmcem.ac.in',
            'Referer': 'https://campus.srmcem.ac.in/psp/ps/?cmd=login'
        }

        # STEP 2: Try logging in
        session = requests.Session()
        response = session.post(login_url, data=payload, headers=headers, timeout=10)
        response.raise_for_status()  # Raises error if status_code >= 400

        # STEP 3: Open attendance page
        attendance_page_url = "https://campus.srmcem.ac.in/psc/ps/EMPLOYEE/HRMS/c/MANAGE_ACADEMIC_RECORDS.STDNT_ATTEND_TERM.GBL?..."

        attendance_response = session.get(attendance_page_url, timeout=10)
        attendance_response.raise_for_status()

        soup = BeautifulSoup(attendance_response.text, 'html.parser')

        # STEP 4: Find ICSID input field
        icsid_input = soup.find('input', {'name': 'ICSID'})
        if not icsid_input:
            context['error'] = "❌ ICSID not found — login/session may have failed."
            return render(request, 'attendamce/home.html', context)

        icsid = icsid_input['value']

        # STEP 5: POST to get attendance data
        attendance_url = "https://campus.srmcem.ac.in/psc/ps/EMPLOYEE/HRMS/c/MANAGE_ACADEMIC_RECORDS.STDNT_ATTEND_TERM.GBL"

        post_payload = {
            "ICAJAX": "1",
            "ICNAVTYPEDROPDOWN": "1",
            "ICType": "Panel",
            "ICElementNum": "0",
            "ICStateNum": "1",
            "ICAction": settings.SEMESTER,
            "ICXPos": "0",
            "ICYPos": "0",
            "ResponsetoDiffFrame": "-1",
            "TargetFrameName": "None",
            "FacetPath": "None",
            "ICFocus": "",
            "ICSaveWarningFilter": "0",
            "ICChanged": "-1",
            "ICResubmit": "0",
            "ICSID": icsid,
            "ICActionPrompt": "false",
            "ICTypeAheadID": "",
            "ICFind": "",
            "ICAddCount": "",
        }

        post_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": attendance_page_url,
            "User-Agent": headers["User-Agent"]
        }

        post_response = session.post(attendance_url, data=post_payload, headers=post_headers, timeout=10)
        post_response.raise_for_status()
        text = post_response.text

        # STEP 6: Find final redirect attendance URL
        match = re.search(r"strCurrUrl='(.*?)'", text)
        if not match:
            context['error'] = "⚠️ Couldn’t find final attendance data URL."
            return render(request, 'attendamce/home.html', context)

        attendance_final_url = match.group(1)
        


        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")       # Comment this to see browser
        options.add_argument('--disable-gpu')

        driver = webdriver.Chrome(options=options)

        # Load base URL to set cookies
        driver.get("https://campus.srmcem.ac.in")

        # Sync session cookies to Selenium
        for cookie in session.cookies:
            driver.add_cookie({
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'secure': cookie.secure,
                'httpOnly': cookie.has_nonstandard_attr('HttpOnly'),
            })

        # Now load the actual attendance page
        driver.get(attendance_final_url)


        try:
            driver.switch_to.frame("ptifrmtgtframe")

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "PERSONAL_DTSAVW_NAME"))
            )
            print("✅ Element found inside iframe.")

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            TOTAL_ATTENDANCE = soup.find('span', {'id': 'SRM_LEAVE_WRK_AMOUNT_DUE'}).get_text(strip=True)

            name_element = driver.find_element(By.ID, "PERSONAL_DTSAVW_NAME")
            name_raw = name_element.text.strip()
            name_parts = name_raw.split(',')
            NAME = f"{name_parts[1].strip()} {name_parts[0].strip()}" if len(name_parts) == 2 else name_raw

            context['name'] = NAME
            context['total_attendance'] = TOTAL_ATTENDANCE



            attendance_url = "https://campus.srmcem.ac.in/psp/ps/EMPLOYEE/HRMS/c/MANAGE_ACADEMIC_RECORDS.STDNT_ATTEND_TERM.GBL?EMPLID=00000021009&INSTITUTION=SRM02&STRM=2301"

            # Count total subject links first
            driver.get(attendance_url)
            WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ptifrmtgtframe")))
            subject_links = driver.find_elements(By.XPATH, "//a[starts-with(@id, 'SELECT$')]")

            total_subjects = len(subject_links) if subject_links else 0

            for i in range(total_subjects):
                try:
                    # Step 1: Load the attendance page fresh
                    driver.get(attendance_url)
                    WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ptifrmtgtframe")))

                    # Step 2: Re-find the subject links
                    subject_links = driver.find_elements(By.XPATH, "//a[starts-with(@id, 'SELECT$')]")
                
                    # Step 3: Click the current subject
                    subject_links[i].click()
                    # print(f"\n➡️ Clicking subject {i}: {subject_links[i].get_attribute('id')}")
                    time.sleep(2)

                    # Step 4: Wait for iframe content to load
                    driver.switch_to.default_content()
                    WebDriverWait(driver, 10).until(
                        EC.frame_to_be_available_and_switch_to_it((By.ID, "ptifrmtgtframe"))
                    )
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "PSXLATITEM_XLATSHORTNAME"))
                    )

                    # Step 5: Parse the attendance info
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    class_type = soup.find('span', {"id": "PSXLATITEM_XLATSHORTNAME"}).get_text(strip=True)
                    subject_name = soup.find('span', {"id": "CLASS_TBL_VW_DESCR"}).get_text(strip=True)

                    # ✅ Initialize context['subjects'] dictionary if not already
                    if 'subjects' not in context:
                        context['subjects'] = {}

                    if 'subject_errors' not in context:
                        context['subject_errors'] = []

                    # ✅ Default values
                    date_text = "N/A"
                    is_present = "N/A"

                    table = soup.find('table', {'id': 'CLASS_ATTENDNCE$scroll$0'})
                    if table:
                        rows = table.find_all("tr", id=lambda x: x and x.startswith("trCLASS_ATTENDNCE"))
                        if rows:
                            last_row = rows[-1]
                            date = last_row.find('span', {'id': lambda x: x and x.startswith('CLASS_ATTENDNCE_CLASS_ATTEND_DT')})
                            checkbox = last_row.find('input', {'type': 'checkbox', 'id': lambda x: x and x.startswith('CLASS_ATTENDNCE_ATTEND_PRESENT')})
                            is_present = checkbox and checkbox.has_attr('checked')
                            date_text = date.get_text(strip=True) if date else "N/A"

                    # ✅ Add to dictionary with subject_name as key
                        subject_key = f"{subject_name} ({class_type})"

                        context['subjects'][subject_key] = {
                            'subject_name': subject_name,
                            'class_type': class_type,
                            'date': date_text,
                            'present': "Present" if is_present else "Absent"
                        }

                except Exception as e:
                        error_msg = f"❌ Error while processing subject {i}: {str(e)}"
                        context['subject_errors'].append(error_msg)




        except:
            context['error'] = "Timed out waiting for final attendance page content or error occurred"
            return render(request, 'attendamce/home.html', context)




        return render(request, 'attendamce/home.html', context)



    except requests.exceptions.RequestException as e:
        # Handles network issues, timeouts, bad HTTP status, etc.
        context['error'] = "🌐 Network error: Please check your internet connection or try again later."
        return render(request, 'attendamce/home.html', context)

    except Exception as e:
        # Catches any other unexpected error (like scraping structure change)
        context['error'] = f"⚠️ Unexpected error occurred: {str(e)}"
        return render(request, 'attendamce/home.html', context)
