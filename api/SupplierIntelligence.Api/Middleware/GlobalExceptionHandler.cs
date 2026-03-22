using System.Net;
using Microsoft.AspNetCore.Diagnostics;
using SupplierIntelligence.Api.Models.DTOs;

namespace SupplierIntelligence.Api.Middleware;

public class GlobalExceptionHandler : IExceptionHandler
{
    private readonly ILogger<GlobalExceptionHandler> _logger;

    public GlobalExceptionHandler(ILogger<GlobalExceptionHandler> logger)
        => _logger = logger;

    public async ValueTask<bool> TryHandleAsync(
        HttpContext context,
        Exception exception,
        CancellationToken cancellationToken)
    {
        _logger.LogError(exception, "Unhandled exception: {Message}", exception.Message);

        var (statusCode, errorType) = exception switch
        {
            KeyNotFoundException => (HttpStatusCode.NotFound, "NOT_FOUND"),
            ArgumentException => (HttpStatusCode.BadRequest, "BAD_REQUEST"),
            InvalidOperationException => (HttpStatusCode.Conflict, "CONFLICT"),
            _ => (HttpStatusCode.InternalServerError, "INTERNAL_ERROR")
        };

        context.Response.StatusCode = (int)statusCode;
        context.Response.ContentType = "application/json";

        var error = new ErrorResponse
        {
            Type = errorType,
            Message = exception.Message,
            Detail = exception.InnerException?.Message,
            Timestamp = DateTime.UtcNow.ToString("O"),
            TraceId = context.TraceIdentifier,
        };

        await context.Response.WriteAsJsonAsync(error, cancellationToken);
        return true;
    }
}
