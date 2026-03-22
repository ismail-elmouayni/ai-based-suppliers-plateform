using Microsoft.EntityFrameworkCore;
using SupplierIntelligence.Api.Models.Entities;

namespace SupplierIntelligence.Api.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    // Views (keyless — read-only)
    public DbSet<VendorScore> VendorScores { get; set; }
    public DbSet<AnomalyFlag> AnomalyFlags { get; set; }

    // Tables with keys
    public DbSet<ConsolidationOpportunity> ConsolidationClusters { get; set; }
    public DbSet<ConsolidationMember> ConsolidationMembers { get; set; }
    public DbSet<MlRunLog> MlRunLogs { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // VendorScores → ai_output.VendorScoresLatest (view)
        modelBuilder.Entity<VendorScore>(e =>
        {
            e.HasNoKey();
            e.ToView("VendorScoresLatest", "ai_output");
            e.Property(p => p.Id).HasColumnName("Id");
            e.Property(p => p.RunId).HasColumnName("RunId");
            e.Property(p => p.CanonicalVendorName).HasColumnName("CanonicalVendorName");
            e.Property(p => p.Category).HasColumnName("Category");
            e.Property(p => p.CompositeScore).HasColumnName("CompositeScore");
            e.Property(p => p.PerformanceBand).HasColumnName("PerformanceBand");
            e.Property(p => p.SavingPctNorm).HasColumnName("SavingPctNorm");
            e.Property(p => p.SpendNorm).HasColumnName("SpendNorm");
            e.Property(p => p.SpecializationNorm).HasColumnName("SpecializationNorm");
            e.Property(p => p.RawSavingPct).HasColumnName("RawSavingPct");
            e.Property(p => p.RawTotalSpend).HasColumnName("RawTotalSpend");
            e.Property(p => p.RawSpecialization).HasColumnName("RawSpecialization");
            e.Property(p => p.POCount).HasColumnName("POCount");
            e.Property(p => p.CreatedAt).HasColumnName("CreatedAt");
        });

        // AnomalyFlags → ai_output.AnomalyFlagsLatest (view)
        modelBuilder.Entity<AnomalyFlag>(e =>
        {
            e.HasNoKey();
            e.ToView("AnomalyFlagsLatest", "ai_output");
            e.Property(p => p.Id).HasColumnName("Id");
            e.Property(p => p.RunId).HasColumnName("RunId");
            e.Property(p => p.SourceRecordId).HasColumnName("SourceRecordId");
            e.Property(p => p.PO_Number).HasColumnName("PO_Number");
            e.Property(p => p.CanonicalVendorName).HasColumnName("CanonicalVendorName");
            e.Property(p => p.Category).HasColumnName("Category");
            e.Property(p => p.Original_Spend).HasColumnName("Original_Spend");
            e.Property(p => p.Spend).HasColumnName("Spend");
            e.Property(p => p.SpendGap).HasColumnName("SpendGap");
            e.Property(p => p.AnomalyScore).HasColumnName("AnomalyScore");
            e.Property(p => p.ZScore).HasColumnName("ZScore");
            e.Property(p => p.Severity).HasColumnName("Severity");
            e.Property(p => p.ReasonString).HasColumnName("ReasonString");
            e.Property(p => p.CreatedAt).HasColumnName("CreatedAt");
        });

        // ConsolidationClusters → ai_output.ConsolidationClusters (table)
        modelBuilder.Entity<ConsolidationOpportunity>(e =>
        {
            e.ToTable("ConsolidationClusters", "ai_output");
            e.HasKey(p => p.Id);
            e.HasMany(p => p.Members)
             .WithOne()
             .HasForeignKey(m => m.ClusterId);
        });

        // ConsolidationMembers → ai_output.ConsolidationMembers (table)
        modelBuilder.Entity<ConsolidationMember>(e =>
        {
            e.ToTable("ConsolidationMembers", "ai_output");
            e.HasKey(p => p.Id);
        });

        // MlRunLog → ml_admin.MlRunLog (table)
        modelBuilder.Entity<MlRunLog>(e =>
        {
            e.ToTable("MlRunLog", "ml_admin");
            e.HasKey(p => p.Id);
        });
    }
}
