"""Healthie EHR integration module.

This module provides functions to interact with Healthie for patient management
and appointment scheduling.
"""

import os
from datetime import date, time as dt_time, datetime

from openai import AsyncOpenAI
from playwright.async_api import async_playwright, Browser, Page
from loguru import logger

client = AsyncOpenAI()

async def login_to_healthie() -> Page:
    """Log into Healthie and return an authenticated page instance.

    This function handles the login process using credentials from environment
    variables. The browser and page instances are stored for reuse by other
    functions in this module.

    Returns:
        Page: An authenticated Playwright Page instance ready for use.

    Raises:
        ValueError: If required environment variables are missing.
        Exception: If login fails for any reason.
    """

    email = os.environ.get("HEALTHIE_EMAIL")
    password = os.environ.get("HEALTHIE_PASSWORD")

    if not email or not password:
        raise ValueError("HEALTHIE_EMAIL and HEALTHIE_PASSWORD must be set in environment variables")

    logger.info("Logging into Healthie...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()

    await page.goto("https://secure.gethealthie.com/users/sign_in", wait_until="domcontentloaded")
    
    # Wait for the email input to be visible
    email_input = page.locator('input[name="identifier"]')
    await email_input.wait_for(state="visible", timeout=30000)
    await email_input.fill(email)

    first_login_button = page.locator('button:has-text("Log In")')
    await first_login_button.wait_for(state="visible", timeout=30000)
    await first_login_button.click()

    
    # Wait for password input
    password_input = page.locator('input[name="password"]')
    await password_input.wait_for(state="visible", timeout=30000)
    await password_input.fill(password)
    
    # Find and click the Log In button
    submit_button = page.locator('button:has-text("Log In")')
    await submit_button.wait_for(state="visible", timeout=30000)
   
    async with page.expect_response(
        lambda r: "auth/v1/user" in r.url and r.status == 200,
        timeout=15000,
    ):
        await submit_button.click()

    logger.info("Successfully logged into Healthie")
    return page


async def find_patient(name: str, date_of_birth: date) -> str | None:
    """Find a patient in Healthie by name and date of birth.

    Args:
        name: The patient's full name.
        date_of_birth: The patient's date of birth.

    Returns:
        str | None: The patient's ID if found, returns None if the patient is not found.

    Raises:
        Exception: If an error occurs.
    """
    page = await login_to_healthie()

    await page.goto("https://secure.gethealthie.com/clients/active", wait_until="domcontentloaded")

    # Wait for search input
    search_input = page.get_by_test_id("search-input")
    await search_input.wait_for(state="visible", timeout=30000)

    await page.wait_for_timeout(1000) # TO DO: Improve this. If we fill the input it too fast, the input is filled but it doesn't trigger a call to the API.

    await search_input.fill(f"{name} - {date_of_birth.isoformat()}")

    await page.wait_for_timeout(5000) # TO DO: Check if the API call has been made instead of just timing out

    # Get the patients list in the search results
    result_links = page.locator("td.client-name-row a")
    count = await result_links.count()
    logger.info(f"Found {count} search results for '{name}'")

    for i in range(count):
        href = await result_links.nth(i).get_attribute("href")
        if href is None:
            continue

        patient_id =  href.split("/")[-1]
        if await is_correct_patient(name, date_of_birth, patient_id, page):
            return patient_id

    return None


async def is_correct_patient(name: str, date_of_birth: date, patient_id: str, page: Page) -> bool:
    await page.goto(f"https://secure.gethealthie.com/users/{patient_id}", wait_until="domcontentloaded")

    dob_el = page.locator('[data-testid="client-dob"]')
    await dob_el.wait_for(state="attached", timeout=10000)
    dob_text = (await dob_el.text_content() or "").strip()

    if not dob_text:
        return False

    try:
        found_dob = datetime.strptime(dob_text, "%b %d, %Y").date()
    except ValueError:
        found_dob = None

    if found_dob != date_of_birth:
        return False

    name_el = page.locator('.sidebar-full-name')
    await name_el.wait_for(state="visible", timeout=10000)
    found_name = await name_el.text_content()

    resp = await client.chat.completions.create( # TO DO: Extract to an LLM Client
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    "Do these two names refer to the same person? "
                    "Example: \"John Doe\" is the same as \"John R. Doe\" but not the same as \"John\" or \"Doe\". "
                    "Answer only 'yes' or 'no'.\n"
                    f"Name 1: {name}\n"
                    f"Name 2: {found_name}"
                ),
            }
        ],
    )
    answer = (resp.choices[0].message.content or "").strip().lower()
    return answer == "yes"


async def create_appointment(patient_id: str, date: date, time: dt_time) -> str:
    """Create an appointment in Healthie for the specified patient and returns the appointment id

    Navigates to the patient's page, opens the appointment dialog, fills
    in the date, time, and appointment type fields, then submits the form.

    Args:
        patient_id: The unique identifier for the patient in Healthie.
        date: The desired appointment date.
        time: The desired appointment time.

    Returns:
        The appointment id.

    Raises:
        RuntimeError: If the appointment creation fails.

    """
    page = await login_to_healthie()

    healthie_date = date.strftime("%B %-d, %Y")  # e.g. "April 6, 2026"
    healthie_time = time.strftime("%-I:%M %p")  # e.g. "12:00 PM"

    logger.info(f"Creating appointment for patient {patient_id} on {healthie_date} at {healthie_time}")

    await page.goto(
        f"https://secure.gethealthie.com/users/{patient_id}",
        wait_until="domcontentloaded",
    )

    add_btn = page.locator('[data-testid="add-appointment-button"]')
    await add_btn.wait_for(state="visible", timeout=30000)
    await add_btn.click()

    # Fill date (React datepicker — triple-click to select all, then type over)
    date_input = page.locator("input#date")
    await date_input.wait_for(state="visible", timeout=10000)
    await date_input.click(click_count=3)
    await date_input.fill(healthie_date)

    # Fill time (React datepicker — same approach)
    time_input = page.locator("input#time")
    await time_input.wait_for(state="visible", timeout=10000)
    await time_input.click(click_count=3)
    await time_input.fill(healthie_time)



    # Select appointment type from React Select dropdown
    type_input = page.locator("input#appointment_type_id")
    await type_input.wait_for(state="visible", timeout=10000)
    await type_input.click()
    await type_input.fill("Initial Consultation")
    option = page.get_by_role("option", name="Initial Consultation - 60 Minutes")
    await option.wait_for(state="visible", timeout=5000)
    await option.click()

    logger.info(f"Appointment fields filled for patient {patient_id}: {healthie_date} at {healthie_time}")

    # Submit appointment
    submit_btn = page.get_by_test_id("appointment-form-modal").get_by_test_id("primaryButton")
    await submit_btn.wait_for(state="visible", timeout=10000)

    async with page.expect_response(
        lambda r: r.url.endswith("/graphql")
        and r.request.method == "POST"
        and "createAppointment" in (r.request.post_data or ""),
        timeout=15000,
    ) as response_info:
        await submit_btn.click()


    # Check graphql response was successful and obtain id
    response = await response_info.value
    body = await response.json()
    gql_result = body[0] if isinstance(body, list) else body
    appointment = gql_result.get("data", {}).get("createAppointment", {}).get("appointment")

    if not appointment:
        raise RuntimeError(f"Appointment creation failed: {gql_result}")

    logger.info(f"Appointment created successfully (id={appointment.get('id')})")

    return appointment.get("id")
