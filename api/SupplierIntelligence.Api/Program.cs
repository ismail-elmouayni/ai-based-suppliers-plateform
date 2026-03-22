using Microsoft.EntityFrameworkCore;
using SupplierIntelligence.Api.Data;
using SupplierIntelligence.Api.Infrastructure;
using SupplierIntelligence.Api.Middleware;
using SupplierIntelligence.Api.Services;

var builder = WebApplication.CreateBuilder(args);

// ── Database ────────────────────────────────────────────────────────────────
var connStr = builder.Configuration.GetConnectionString("DefaultConnection")!
    .Replace("${MSSQL_SA_PASSWORD}", Environment.GetEnvironmentVariable("MSSQL_SA_PASSWORD") ?? "");

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connStr, sqlOpts =>
    {
        sqlOpts.EnableRetryOnFailure(5, TimeSpan.FromSeconds(10), null);
        sqlOpts.CommandTimeout(60);
    }));

// ── HTTP Client for ML Engine ────────────────────────────────────────────────
var mlBaseUrl = builder.Configuration["MlEngine:BaseUrl"] ?? "http://ml-engine:5001";
builder.Services.AddHttpClient("MlEngine", c =>
{
    c.BaseAddress = new Uri(mlBaseUrl);
    c.Timeout = TimeSpan.FromSeconds(30);
});

// ── Services ─────────────────────────────────────────────────────────────────
builder.Services.AddScoped<IVendorRankingService, VendorRankingService>();
builder.Services.AddScoped<IConsolidationService, ConsolidationService>();
builder.Services.AddScoped<IAnomalyDetectionService, AnomalyDetectionService>();
builder.Services.AddScoped<IMlTriggerService, MlTriggerService>();
builder.Services.AddSingleton<ConfigSummaryReader>();

// ── MVC + Swagger ────────────────────────────────────────────────────────────
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new()
    {
        Title = "Supplier Intelligence API",
        Version = "v1",
        Description = "AI-Powered Supplier Intelligence Platform — REST API",
    });
});

// ── Exception handler ─────────────────────────────────────────────────────────
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();

var app = builder.Build();

// ── Middleware pipeline ───────────────────────────────────────────────────────
app.UseExceptionHandler();

app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "Supplier Intelligence API v1");
    c.RoutePrefix = "swagger";
});

app.MapControllers();

// Redirect root → swagger
app.MapGet("/", () => Results.Redirect("/swagger"));

app.Run();
