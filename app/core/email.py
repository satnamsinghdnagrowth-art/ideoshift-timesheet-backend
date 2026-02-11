import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import os


class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@ideoshift.com")
        self.smtp_from_name = os.getenv("SMTP_FROM_NAME", "Ideoshift")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email using SMTP"""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
            msg["To"] = to_email

            # Add text and HTML parts
            if text_content:
                part1 = MIMEText(text_content, "plain")
                msg.attach(part1)

            part2 = MIMEText(html_content, "html")
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        """Send password reset email with professional template"""
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        subject = "Reset Your Ideoshift Password"
        
        # Professional HTML email template with responsive design
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="IE=edge">
            <title>Password Reset - Ideoshift</title>
            <!--[if mso]>
            <style type="text/css">
                body, table, td {{font-family: Arial, sans-serif !important;}}
            </style>
            <![endif]-->
        </head>
        <body style="margin: 0; padding: 0; background-color: #f4f4f7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f4f4f7; padding: 40px 0;">
                <tr>
                    <td align="center">
                        <!-- Main Container -->
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); overflow: hidden;">
                            
                            <!-- Header with Logo and Brand -->
                            <tr>
                                <td style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); padding: 40px 30px; text-align: center;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        <tr>
                                            <td style="text-align: center;">
                                                <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700; letter-spacing: -0.5px;">
                                                    Ideoshift
                                                </h1>
                                                <p style="margin: 8px 0 0 0; color: #e3f2fd; font-size: 14px; font-weight: 400;">
                                                    Timesheet & Attendance Management
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            
                            <!-- Main Content -->
                            <tr>
                                <td style="padding: 50px 40px;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        <tr>
                                            <td style="padding-bottom: 30px;">
                                                <h2 style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 24px; font-weight: 600; line-height: 1.3;">
                                                    Password Reset Request
                                                </h2>
                                                <p style="margin: 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                                    Hello,
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding-bottom: 25px;">
                                                <p style="margin: 0 0 16px 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                                    We received a request to reset the password for your <strong>Ideoshift</strong> account. If you made this request, click the button below to proceed.
                                                </p>
                                                <p style="margin: 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                                    If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 30px 0; text-align: center;">
                                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center">
                                                    <tr>
                                                        <td style="border-radius: 6px; background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); text-align: center;">
                                                            <a href="{reset_link}" target="_blank" style="display: inline-block; padding: 16px 40px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; letter-spacing: 0.5px;">
                                                                Reset Password
                                                            </a>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 25px 0; border-top: 1px solid #e2e8f0;">
                                                <p style="margin: 0 0 12px 0; color: #718096; font-size: 14px; line-height: 1.5;">
                                                    <strong>Having trouble clicking the button?</strong> Copy and paste this URL into your browser:
                                                </p>
                                                <p style="margin: 0; padding: 12px; background-color: #f7fafc; border: 1px solid #e2e8f0; border-radius: 4px; color: #1976d2; font-size: 13px; word-break: break-all; font-family: 'Courier New', monospace;">
                                                    {reset_link}
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 20px 0;">
                                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                                                    <tr>
                                                        <td style="padding: 16px 20px;">
                                                            <p style="margin: 0; color: #856404; font-size: 14px; line-height: 1.5;">
                                                                <strong>⏰ Important:</strong> This password reset link will expire in <strong>1 hour</strong> for security reasons.
                                                            </p>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding-top: 25px; border-top: 1px solid #e2e8f0;">
                                                <p style="margin: 0; color: #718096; font-size: 14px; line-height: 1.6;">
                                                    If you have any questions or concerns, please contact our support team.
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            
                            <!-- Footer -->
                            <tr>
                                <td style="background-color: #f7fafc; padding: 30px 40px; border-top: 1px solid #e2e8f0;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                        <tr>
                                            <td style="text-align: center; padding-bottom: 15px;">
                                                <p style="margin: 0; color: #4a5568; font-size: 16px; font-weight: 600;">
                                                    Ideoshift
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="text-align: center; padding-bottom: 10px;">
                                                <p style="margin: 0; color: #718096; font-size: 13px; line-height: 1.5;">
                                                    © 2026 Ideoshift. All rights reserved.
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="text-align: center;">
                                                <p style="margin: 0; color: #a0aec0; font-size: 12px; line-height: 1.5;">
                                                    This is an automated message. Please do not reply to this email.
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        # Plain text version for email clients that don't support HTML
        text_content = f"""
Password Reset Request - Ideoshift
{'=' * 50}

Hello,

We received a request to reset the password for your Ideoshift account.

If you made this request, please visit the following link to reset your password:

{reset_link}

If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.

IMPORTANT: This password reset link will expire in 1 hour for security reasons.

If you have any questions or concerns, please contact our support team.

{'=' * 50}
© 2026 Ideoshift. All rights reserved.
This is an automated message. Please do not reply to this email.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)


# Singleton instance
email_service = EmailService()
