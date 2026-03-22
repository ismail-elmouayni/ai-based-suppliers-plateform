namespace SupplierIntelligence.Api.Models.DTOs;

public class ErrorResponse
{
    public string Type { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public string? Detail { get; set; }
    public string Timestamp { get; set; } = DateTime.UtcNow.ToString("O");
    public string? TraceId { get; set; }
}
