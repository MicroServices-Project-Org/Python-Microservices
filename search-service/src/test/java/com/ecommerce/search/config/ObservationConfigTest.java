package com.ecommerce.search.config;

import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationPredicate;
import org.junit.jupiter.api.Test;
import org.springframework.http.server.observation.ServerRequestObservationContext;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;

class ObservationConfigTest {

    private final ObservationPredicate predicate = new ObservationConfig().skipActuatorTracing();

    private boolean observed(String uri) {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", uri);
        return predicate.test("http.server.requests",
                new ServerRequestObservationContext(request, new MockHttpServletResponse()));
    }

    @Test
    void skipsActuatorEndpoints() {
        assertThat(observed("/actuator/prometheus")).isFalse();
        assertThat(observed("/actuator/health")).isFalse();
    }

    @Test
    void keepsApiRequests() {
        assertThat(observed("/api/search")).isTrue();
    }

    @Test
    void keepsNonHttpObservations() {
        // Kafka listener and @Scheduled observations use other context types
        assertThat(predicate.test("tasks.scheduled.execution", new Observation.Context())).isTrue();
    }
}
