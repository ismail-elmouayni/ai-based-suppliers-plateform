namespace SupplierIntelligence.Api.Models.Entities;

public class MlRunLog
{
    public long Id { get; set; }
    public string RunType { get; set; } = string.Empty;
    public string? TriggeredBy { get; set; }
    public string Status { get; set; } = string.Empty;
    public DateTime StartedAt { get; set; }
    public DateTime? CompletedAt { get; set; }
    public long? DurationMs { get; set; }
    public string? ErrorMessage { get; set; }
    public string? ConfigSnapshot { get; set; }
}
