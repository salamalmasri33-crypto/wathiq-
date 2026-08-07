using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.Extensions.Configuration;
using System.Net;
using System.Net.Mail;

namespace eArchiveSystem.Application.Services
{
    public class EmailService : IEmailService
    {
        private readonly IConfiguration _config;

        public EmailService(IConfiguration config)
        {
            _config = config;
        }

        public async Task SendEmailAsync(string to, string subject, string body)
        {
            var settings = _config.GetSection("EmailSettings");

            var message = new MailMessage();
            message.From = new MailAddress(settings["From"]);
            message.To.Add(to);
            message.Subject = subject;
            message.Body = body;
            message.IsBodyHtml = true;

            using var smtp = new SmtpClient(settings["Host"], int.Parse(settings["Port"]))
            {
                Credentials = new NetworkCredential(settings["From"], settings["Password"]),
                EnableSsl = true
            };

            await smtp.SendMailAsync(message);
        }
    }
}
