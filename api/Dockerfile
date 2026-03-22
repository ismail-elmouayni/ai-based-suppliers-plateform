# Multi-stage Dockerfile — .NET 8 API
# Stage: build   – compile with SDK
# Stage: runtime – minimal ASP.NET runtime image

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Restore dependencies
COPY SupplierIntelligence.Api/SupplierIntelligence.Api.csproj SupplierIntelligence.Api/
RUN dotnet restore SupplierIntelligence.Api/SupplierIntelligence.Api.csproj

# Build and publish
COPY . .
RUN dotnet publish SupplierIntelligence.Api/SupplierIntelligence.Api.csproj \
    -c Release -o /app/publish

# ── runtime stage ──────────────────────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

# Install curl for health checks (not included in the minimal aspnet image)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/admin/health || exit 1

ENTRYPOINT ["dotnet", "SupplierIntelligence.Api.dll"]
