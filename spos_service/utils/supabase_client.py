from supabase import create_client
import os

# Supabase credentials
SUPABASE_URL = "https://kkumtobyfyelwoozdxre.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtrdW10b2J5ZnllbHdvb3pkeHJlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mjk2OTMxMTEsImV4cCI6MjA0NTI2OTExMX0.utb-Btz7YlN3SQbfRjiuGlbManzlvSvyygJsTrhAPbU"

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_data(table: str, select_query: str = "*"):
    """
    Fetch data from a Supabase table.

    Args:
        table (str): Name of the table to fetch data from.
        select_query (str): Query specifying columns to retrieve. Default is all (*).

    Returns:
        list: List of rows from the table.
    """
    response = supabase.table(table).select(select_query).execute()
    return response.data  # Return the retrieved data

def insert_data(table: str, data: dict):
    """
    Insert a new record into a Supabase table.

    Args:
        table (str): Name of the table to insert data into.
        data (dict): A dictionary representing the record to be inserted.

    Returns:
        dict: Inserted record from the database.
    """
    response = supabase.table(table).insert(data).execute()
    return response.data  # Return the inserted record

def update_data(table: str, match: dict, data: dict):
    """
    Update records in a Supabase table.

    Args:
        table (str): Name of the table to update data in.
        match (dict): A dictionary specifying the matching condition (e.g., {"id": 1}).
        data (dict): A dictionary representing the fields to be updated.

    Returns:
        dict: Updated records from the database.
    """
    response = supabase.table(table).update(data).match(match).execute()
    return response.data  # Return the updated records

def delete_data(table: str, match: dict):
    """
    Delete records from a Supabase table.

    Args:
        table (str): Name of the table to delete data from.
        match (dict): A dictionary specifying the matching condition (e.g., {"id": 1}).

    Returns:
        dict: Confirmation of deletion.
    """
    response = supabase.table(table).delete().match(match).execute()
    return response.data  # Return the deleted records


def fetch_with_date_range(table: str, start_date: str, end_date: str, select_query: str = "*"):
    """
    Fetch appointments from a Supabase table within a specific date range.

    Args:
        table (str): Name of the table to fetch data from.
        start_date (str): Start date for the range (YYYY-MM-DD).
        end_date (str): End date for the range (YYYY-MM-DD).
        select_query (str): Query specifying columns to retrieve. Default is all (*).

    Returns:
        list: List of rows from the table.
    """
    response = supabase.table(table)\
        .select(select_query)\
        .filter("start_time", "gte", start_date)\
        .filter("start_time", "lte", end_date)\
        .execute()
    return response.data