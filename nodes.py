

from pipecat_flows import FlowsFunctionSchema, NodeConfig
from pipecat_flows import FlowArgs

from dateutil import parser as dateutil_parser
from loguru import logger

from healthie import find_patient, create_appointment

def create_greet_and_collect_patient_info_node() -> NodeConfig:
    """Create the greeting node that collects patient name and date of birth."""

    async def collect_patient_info(args: FlowArgs) -> tuple[None, NodeConfig]:
        name = args["name"]
        date_of_birth = args["date_of_birth"]
        return None, create_lookup_node(name, date_of_birth)

    collect_patient_info_schema = FlowsFunctionSchema(
        name="collect_patient_info",
        description="Collect the patient's name and date of birth",
        properties={
            "name": {"type": "string"},
            "date_of_birth": {"type": "string"},
        },
        required=["name", "date_of_birth"],
        handler=collect_patient_info,
    )

    return NodeConfig(
        name="greet_and_collect_patient_info",
        role_messages=[
            {
                "role": "system",
                "content": "You are a digital assistant from the Prosper Health clinic. Be casual and friendly. This is a voice conversation, so avoid special characters and emojis.",
            }
        ],
        task_messages=[
            {
                "role": "user",
                "content": "Say hello and briefly introduce yourself as a digital assistant from the Prosper Health clinic. Ask for the patient's name and date of birth. This is your only job for now; if the customer asks for something else, politely remind them you can't do it.",
            }
        ],
        functions=[collect_patient_info_schema],
        respond_immediately=True,
    )


def create_lookup_node(name: str, date_of_birth: str) -> NodeConfig:
    """Intermediate node that speaks a 'looking you up' message, then does the actual API lookup."""

    async def do_lookup(args: FlowArgs) -> tuple[None, NodeConfig]:
        try:
            dob = dateutil_parser.parse(date_of_birth).date()
        except (ValueError, OverflowError) as e:
            logger.error(f"Failed to parse date of birth '{date_of_birth}': {e}")
            return None, create_greet_and_collect_patient_info_node()

        try:
            patient_id = await find_patient(name, dob)
        except Exception as e:
            logger.error(f"Patient lookup failed: {e}")
            return None, create_unsuccessful_end_node_patient_not_found()

        if patient_id is None:
            return None, create_unsuccessful_end_node_patient_not_found()
        return None, create_schedule_node(patient_id)

    do_lookup_schema = FlowsFunctionSchema(
        name="do_lookup",
        description="Look up the patient in the system",
        properties={},
        required=[],
        handler=do_lookup,
    )

    return NodeConfig(
        name="lookup_patient",
        task_messages=[
            {
                "role": "user",
                "content": "Tell the patient you're looking up their record. Now call do_lookup immediately to search for them.",
            }
        ],
        functions=[do_lookup_schema],
    )


def create_schedule_node(patient_id: str) -> NodeConfig:
    """Create the scheduling node that collects a date and time for the appointment."""

    async def collect_schedule(args: FlowArgs) -> tuple[None, NodeConfig]:
        return None, create_booking_node(patient_id, args["date"], args["time"])

    collect_schedule_schema = FlowsFunctionSchema(
        name="collect_schedule",
        description="Collect the date and time the patient wants for their appointment",
        properties={
            "date": {"type": "string", "description": "Appointment date, e.g. 'April 10, 2026'"},
            "time": {"type": "string", "description": "Appointment time, e.g. '2:30 PM'"},
        },
        required=["date", "time"],
        handler=collect_schedule,
    )

    return NodeConfig(
        name="schedule",
        task_messages=[
            {
                "role": "user",
                "content": "Great news — the patient's record was found. Now ask them what date and time they'd like to schedule an appointment. Once they provide both, call collect_schedule.",
            }
        ],
        functions=[collect_schedule_schema],
    )


def create_booking_node(patient_id: str, date: str, time: str) -> NodeConfig:
    """Intermediate node that tells the patient it's booking, then does the actual API call."""

    async def do_booking(args: FlowArgs) -> tuple[None, NodeConfig]:
        try:
            parsed_dt = dateutil_parser.parse(f"{date} {time}")
        except (ValueError, OverflowError) as e:
            logger.error(f"Failed to parse appointment date/time '{date} {time}': {e}")
            return None, create_schedule_node(patient_id)

        try:
            await create_appointment(
                patient_id,
                parsed_dt.date(),
                parsed_dt.time(),
            )
        except Exception as e:
            logger.error(f"Appointment creation failed: {e}")
            return None, create_unsuccessful_end_node_assignment_creation_failed()

        return None, create_successful_end_node(
            appointment_date=parsed_dt.date().isoformat(),
            appointment_time=parsed_dt.time().isoformat(),
        )

    do_booking_schema = FlowsFunctionSchema(
        name="do_booking",
        description="Book the appointment in the system",
        properties={},
        required=[],
        handler=do_booking,
    )

    return NodeConfig(
        name="booking",
        task_messages=[
            {
                "role": "user",
                "content": "Tell the patient you're booking their appointment now. Then call do_booking immediately.",
            }
        ],
        functions=[do_booking_schema],
    )

def create_unsuccessful_end_node_assignment_creation_failed() -> NodeConfig:
    return NodeConfig(
        name="unsuccessful_end_node_assignment_creation_failed",
        task_messages=[
            {
                "role": "user",
                "content": "Something went wrong. Tell the patient and end the conversation.",
            }
        ],
        post_actions=[{"type": "end_conversation"}],
    )

def create_unsuccessful_end_node_patient_not_found() -> NodeConfig:
    """Create the unsuccessful end node that tells the patient their record was not found and ends the conversation."""
    return NodeConfig(
        name="unsuccessful_end_node_patient_not_found",
        task_messages=[
            {
                "role": "user",
                "content": "The patient's record was not found. Tell the patient and end the conversation.",
            }
        ],
        post_actions=[{"type": "end_conversation"}],
    )


def create_successful_end_node(appointment_date: str, appointment_time: str) -> NodeConfig:
    """Create the final node that confirms the booking and ends."""
    return NodeConfig(
        name="end_node",
        task_messages=[
            {
                "role": "user",
                "content": f"Tell the patient their appointment has been booked for {appointment_date} at {appointment_time}. Thank them and end the conversation.",
            }
        ],
        post_actions=[{"type": "end_conversation"}],
    )
