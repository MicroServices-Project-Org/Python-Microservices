package com.ecommerce.search.config;

import io.micrometer.observation.ObservationPredicate;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.server.observation.ServerRequestObservationContext;

@Configuration
public class ObservationConfig {

    /**
     * Don't trace /actuator requests. Prometheus scrapes /actuator/prometheus every 15s and
     * the Docker healthcheck hits /actuator/health, which would bury real traces in Tempo.
     * This also drops them from the http.server.requests metrics, which only matter for API routes.
     */
    @Bean
    ObservationPredicate skipActuatorTracing() {
        return (name, context) -> !(context instanceof ServerRequestObservationContext request
                && request.getCarrier().getRequestURI().startsWith("/actuator"));
    }
}
