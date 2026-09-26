# ─────────────────────────────────────────────
# Stage 1 — Build the jar (no prebuilt target/ needed)
# ─────────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src/ ./src/
RUN mvn -q -B package -DskipTests

# ─────────────────────────────────────────────
# Stage 2 — Runtime
# ─────────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/search-service-1.0.0.jar app.jar
RUN adduser -D appuser
USER appuser
EXPOSE 8006
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://localhost:8006/actuator/health"]
ENTRYPOINT ["java", "-jar", "app.jar"]
