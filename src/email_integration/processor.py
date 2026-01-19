"""
Email integration module for reading and analyzing emails.

Provides secure email access with LLM-powered analysis for news briefs and todo suggestions.
"""

import imaplib
import email
import email.header
import json
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from config import config
from memory import TelosManager
from ollama import OllamaClient
from utils import get_logger


logger = get_logger(__name__)


class EmailConfigError(Exception):
    """Email configuration errors."""
    pass


class EmailConnectionError(Exception):
    """Email connection errors."""
    pass


class EmailProcessor:
    """Processes emails and generates insights using LLM."""

    def __init__(self):
        """Initialize the email processor."""
        self.telos = TelosManager()
        self.ollama = OllamaClient()

        # Email processing configuration
        self.days_back = 7  # Only process emails from last 7 days
        self.max_emails = 50  # Maximum emails to process per run
        self.processed_emails_file = Path(config.memory_dir) / "processed_emails.jsonl"

    def process_emails(
        self,
        server: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True
    ) -> Dict[str, Any]:
        """
        Process recent emails and generate insights.

        Args:
            server: IMAP server address
            port: IMAP server port
            username: Email username
            password: Email password
            use_ssl: Whether to use SSL

        Returns:
            Dictionary with processing results and insights
        """
        logger.info(f"Starting email processing from {server}:{port}")

        results = {
            'success': False,
            'emails_processed': 0,
            'news_brief': '',
            'suggested_todos': [],
            'errors': [],
            'connection_status': 'connecting'
        }

        try:
            # Connect to email server
            mail = imaplib.IMAP4_SSL(server, port) if use_ssl else imaplib.IMAP4(server, port)
            mail.login(username, password)
            mail.select('INBOX', readonly=True)  # Read-only to preserve unread status

            results['connection_status'] = 'connected'

            # Search for recent emails
            since_date = (datetime.now() - timedelta(days=self.days_back)).strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'SINCE {since_date}')

            if status != 'OK':
                raise EmailConnectionError(f"Failed to search emails: {status}")

            email_ids = messages[0].split()
            email_ids = email_ids[-self.max_emails:]  # Get most recent emails

            logger.info(f"Found {len(email_ids)} recent emails to process")

            # Process emails (don't mark as processed yet)
            processed_emails = []
            for email_id in email_ids:
                try:
                    email_data = self._process_single_email(mail, email_id)
                    if email_data and not self._is_email_processed(email_data['message_id']):
                        processed_emails.append(email_data)
                except Exception as e:
                    logger.warning(f"Failed to process email {email_id}: {e}")
                    results['errors'].append(f"Email {email_id}: {str(e)}")

            mail.close()
            mail.logout()

            results['connection_status'] = 'disconnected'

            if processed_emails:
                # Generate insights using LLM
                try:
                    insights = self._generate_email_insights(processed_emails)
                    results.update(insights)
                    results['success'] = True

                    # Only mark emails as processed after successful LLM analysis
                    for email_data in processed_emails:
                        self._mark_email_processed(email_data['message_id'])

                    results['emails_processed'] = len(processed_emails)
                    logger.info(f"Email processing complete: {len(processed_emails)} emails processed with insights")

                except Exception as e:
                    # LLM analysis failed - don't mark emails as processed so they can be retried
                    results['emails_processed'] = 0
                    results['errors'].append(f"LLM analysis failed: {str(e)}")
                    results['news_brief'] = f"Processed {len(processed_emails)} emails but analysis failed: {str(e)}"
                    logger.error(f"LLM analysis failed: {e}")
            else:
                results['emails_processed'] = 0
                logger.info("Email processing complete: no new emails to process")

        except imaplib.IMAP4.error as e:
            results['connection_status'] = 'failed'
            results['errors'].append(f"IMAP error: {str(e)}")
            logger.error(f"IMAP connection failed: {e}")
        except Exception as e:
            results['connection_status'] = 'failed'
            results['errors'].append(f"Unexpected error: {str(e)}")
            logger.error(f"Email processing failed: {e}")

        return results

    def _process_single_email(self, mail: imaplib.IMAP4, email_id: bytes) -> Optional[Dict[str, Any]]:
        """Process a single email message."""
        try:
            status, msg_data = mail.fetch(email_id.decode(), '(RFC822)')
            if status != 'OK':
                return None

            if not msg_data or not msg_data[0] or len(msg_data[0]) < 2:
                return None

            email_body = msg_data[0][1]
            if not email_body:
                return None

            # Ensure it's bytes for email parsing
            if isinstance(email_body, str):
                email_body = email_body.encode('utf-8')
            elif not isinstance(email_body, bytes):
                return None

            email_message = email.message_from_bytes(email_body)

            # Extract email information
            subject = self._decode_header(email_message.get('Subject', ''))
            sender = self._decode_header(email_message.get('From', ''))
            date = email_message.get('Date', '')
            message_id = email_message.get('Message-ID', '')

            # Extract body text
            body_text = self._extract_body_text(email_message)

            return {
                'message_id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body_preview': body_text[:500] + '...' if len(body_text) > 500 else body_text,
                'body_full': body_text
            }

        except Exception as e:
            logger.warning(f"Error processing email {email_id}: {e}")
            return None

    def _decode_header(self, header: str) -> str:
        """Decode email header with proper encoding handling."""
        try:
            decoded = email.header.decode_header(header)
            result = ''
            for part, encoding in decoded:
                if isinstance(part, bytes):
                    result += part.decode(encoding or 'utf-8', errors='ignore')
                else:
                    result += str(part)
            return result
        except Exception:
            return header

    def _extract_body_text(self, email_message) -> str:
        """Extract plain text body from email message."""
        body_text = ''

        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == 'text/plain':
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        body_text = part.get_payload(decode=True).decode(charset, errors='ignore')
                        break
                    except Exception:
                        continue
        else:
            if email_message.get_content_type() == 'text/plain':
                charset = email_message.get_content_charset() or 'utf-8'
                try:
                    body_text = email_message.get_payload(decode=True).decode(charset, errors='ignore')
                except Exception:
                    body_text = str(email_message.get_payload())

        return body_text.strip()

    def _is_email_processed(self, message_id: str) -> bool:
        """Check if an email has already been processed."""
        if not self.processed_emails_file.exists():
            return False

        try:
            with open(self.processed_emails_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        processed = json.loads(line)
                        if processed.get('message_id') == message_id:
                            return True
        except Exception as e:
            logger.warning(f"Error checking processed emails: {e}")

        return False

    def _mark_email_processed(self, message_id: str) -> None:
        """Mark an email as processed."""
        try:
            processed_record = {
                'message_id': message_id,
                'processed_at': datetime.now().isoformat(),
                'processor_version': '1.0'
            }

            with open(self.processed_emails_file, 'a', encoding='utf-8') as f:
                json.dump(processed_record, f, ensure_ascii=False)
                f.write('\n')

        except Exception as e:
            logger.warning(f"Error marking email as processed: {e}")

    def _generate_email_insights(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate insights from emails using LLM."""
        if not emails:
            return {'news_brief': '', 'suggested_todos': []}

        # Create email summary for LLM
        email_summary = "Recent emails:\n\n"
        for i, email_data in enumerate(emails[:10], 1):  # Limit to 10 emails for summary
            email_summary += f"{i}. From: {email_data['sender']}\n"
            email_summary += f"   Subject: {email_data['subject']}\n"
            email_summary += f"   Content: {email_data['body_preview']}\n\n"

        # Get existing todos to avoid duplicates
        existing_todos = self._get_existing_todos_summary()

        # Create LLM prompt
        prompt = f"""
You are a personal assistant analyzing recent emails. Your task is to:

1. Create a brief news summary of important emails
2. Suggest actionable todo items based on email content
3. IMPORTANT: Check if suggested todos already exist in the current todo list

Current Todo List:
{existing_todos}

Email Summary:
{email_summary}

Please respond with a JSON object containing:
- "news_brief": A 2-3 sentence summary of key emails
- "suggested_todos": Array of todo suggestions (only if they don't already exist)

Each todo should have:
- "content": Brief description
- "priority": "low", "medium", or "high"
- "reason": Why this todo is needed based on emails

Only suggest todos that are genuinely new and actionable.
"""

        try:
            # Get LLM analysis
            response = self.ollama.generate_text(prompt, model=config.ollama_model)

            # Parse JSON response
            try:
                # Ensure response is a string
                response_str = str(response) if not isinstance(response, str) else response
                parsed = json.loads(response_str)
                news_brief = parsed.get('news_brief', 'No summary available')
                suggested_todos = parsed.get('suggested_todos', [])
            except (json.JSONDecodeError, TypeError):
                # Fallback parsing
                news_brief = "Email analysis completed but summary format was unclear."
                suggested_todos = []

            # Filter out duplicates
            filtered_todos = []
            for todo in suggested_todos:
                if not self._is_todo_duplicate(todo.get('content', '')):
                    filtered_todos.append(todo)

            return {
                'news_brief': news_brief,
                'suggested_todos': filtered_todos
            }

        except Exception as e:
            logger.error(f"Failed to generate email insights: {e}")
            return {
                'news_brief': f'Processed {len(emails)} emails but analysis failed: {str(e)}',
                'suggested_todos': []
            }

    def _get_existing_todos_summary(self) -> str:
        """Get summary of existing todos to avoid duplicates."""
        try:
            tasks = self.telos.get_tasks()
            if not tasks:
                return "No existing tasks."

            summary = "Existing Tasks:\n"
            for task in tasks[:10]:  # Show up to 10
                content = task.get('content', '')[:100]
                status = task.get('status', 'unknown')
                summary += f"- [{status}] {content}\n"

            return summary

        except Exception as e:
            logger.warning(f"Error getting existing todos: {e}")
            return "Unable to check existing tasks."

    def _is_todo_duplicate(self, todo_content: str) -> bool:
        """Check if a suggested todo already exists."""
        try:
            existing_tasks = self.telos.get_tasks()
            todo_lower = todo_content.lower()

            for task in existing_tasks:
                task_content = task.get('content', '').lower()
                # Simple fuzzy matching - check for significant overlap
                if self._content_similarity(todo_lower, task_content) > 0.7:
                    return True

            return False

        except Exception as e:
            logger.warning(f"Error checking todo duplicates: {e}")
            return False  # Assume not duplicate if check fails

    def _content_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity between two texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)