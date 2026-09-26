package com.ecommerce.search.service;

import org.springframework.data.elasticsearch.core.query.Query;
import com.ecommerce.search.model.Product;
import com.ecommerce.search.repository.ProductSearchRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.elasticsearch.core.ElasticsearchOperations;
import org.springframework.data.elasticsearch.core.SearchHit;
import org.springframework.data.elasticsearch.core.SearchHits;
// import org.springframework.data.elasticsearch.core.SearchHitsImpl;
// import org.springframework.data.elasticsearch.core.TotalHitsRelation;
import org.springframework.data.elasticsearch.core.query.Criteria;
import org.springframework.data.elasticsearch.core.query.CriteriaQuery;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class SearchServiceTest {

    @Mock
    private ProductSearchRepository repository;

    @Mock
    private ElasticsearchOperations elasticsearchOperations;

    @InjectMocks
    private SearchService searchService;

    private Product sampleProduct;

    @BeforeEach
    void setUp() {
        sampleProduct = Product.builder()
                .id("prod-001")
                .name("iPhone 15 Pro")
                .description("Latest Apple smartphone")
                .price(999.99)
                .category("Electronics")
                .tags(List.of("smartphone", "apple"))
                .stockQuantity(100)
                .build();
    }

    // ─── Helper ─────────────────────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    private SearchHits<Product> mockSearchHits(List<Product> products) {
        SearchHits<Product> hits = mock(SearchHits.class);
        List<SearchHit<Product>> hitList = products.stream()
                .map(p -> {
                    SearchHit<Product> hit = mock(SearchHit.class);
                    when(hit.getContent()).thenReturn(p);
                    return hit;
                })
                .toList();
        when(hits.getSearchHits()).thenReturn(hitList);
        return hits;
    }

    // ─── search ─────────────────────────────────────────────────────────────

    @Test
    void search_returnsMatchingProducts() {
        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<Product> results = searchService.search("iPhone");

        assertEquals(1, results.size());
        assertEquals("iPhone 15 Pro", results.get(0).getName());
    }

    @Test
    void search_returnsEmptyListWhenNoMatch() {
        SearchHits<Product> hits = mockSearchHits(List.of());
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<Product> results = searchService.search("nonexistent");

        assertTrue(results.isEmpty());
    }

    @Test
    void search_returnsMultipleResults() {
        Product product2 = Product.builder()
                .id("prod-002")
                .name("iPhone 15")
                .price(799.99)
                .category("Electronics")
                .build();

        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct, product2));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<Product> results = searchService.search("iPhone");

        assertEquals(2, results.size());
    }

    // ─── autocomplete ───────────────────────────────────────────────────────

    @Test
    void autocomplete_returnsSuggestions() {
        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<String> suggestions = searchService.autocomplete("iPh");

        assertFalse(suggestions.isEmpty());
        assertTrue(suggestions.contains("iPhone 15 Pro"));
    }

    @Test
    void autocomplete_returnsEmptyForNoMatch() {
        SearchHits<Product> hits = mockSearchHits(List.of());
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<String> suggestions = searchService.autocomplete("xyz");

        assertTrue(suggestions.isEmpty());
    }

    @Test
    void autocomplete_returnsDistinctNames() {
        Product dup = Product.builder()
                .id("prod-003")
                .name("iPhone 15 Pro")
                .price(999.99)
                .build();

        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct, dup));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<String> suggestions = searchService.autocomplete("iPh");

        assertEquals(1, suggestions.size());
    }

    @Test
    void autocomplete_multiWordMatchesEachWordWithoutWhitespace() {
        // Criteria.contains() can't take whitespace ("Cannot constructQuery"), so each word gets its own criterion
        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<String> suggestions = searchService.autocomplete("  iPhone   15 ");

        ArgumentCaptor<Query> captor = ArgumentCaptor.forClass(Query.class);
        verify(elasticsearchOperations).search(captor.capture(), eq(Product.class));
        List<Criteria> chain = ((CriteriaQuery) captor.getValue()).getCriteria().getCriteriaChain();
        List<Object> values = chain.stream()
                .flatMap(c -> c.getQueryCriteriaEntries().stream())
                .map(Criteria.CriteriaEntry::getValue)
                .toList();
        assertEquals(List.of("iPhone", "15"), values);
        assertTrue(chain.stream().allMatch(c -> "name".equals(c.getField().getName())));
        assertEquals(List.of("iPhone 15 Pro"), suggestions);
    }

    @Test
    void autocomplete_blankQueryReturnsEmptyWithoutSearching() {
        assertTrue(searchService.autocomplete("   ").isEmpty());
        verifyNoInteractions(elasticsearchOperations);
    }

    // ─── filter ─────────────────────────────────────────────────────────────

    @Test
    void filter_byCategoryReturnsResults() {
        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<Product> results = searchService.filter("Electronics", null, null);

        assertEquals(1, results.size());
        assertEquals("Electronics", results.get(0).getCategory());
    }

    @Test
    void filter_byPriceRangeReturnsResults() {
        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<Product> results = searchService.filter(null, 500.0, 1500.0);

        assertEquals(1, results.size());
    }

    @Test
    void filter_byCategoryAndPriceReturnsResults() {
        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<Product> results = searchService.filter("Electronics", 500.0, 1500.0);

        assertEquals(1, results.size());
    }

    @Test
    void filter_noFiltersReturnsAll() {
        SearchHits<Product> hits = mockSearchHits(List.of(sampleProduct));
        when(elasticsearchOperations.search(any(Query.class), eq(Product.class)))
                .thenReturn(hits);

        List<Product> results = searchService.filter(null, null, null);

        assertFalse(results.isEmpty());
    }

    // ─── indexProduct ───────────────────────────────────────────────────────

    @Test
    void indexProduct_savesAndReturnsProduct() {
        when(repository.save(any(Product.class))).thenReturn(sampleProduct);

        Product result = searchService.indexProduct(sampleProduct);

        assertNotNull(result);
        assertEquals("iPhone 15 Pro", result.getName());
        verify(repository).save(any(Product.class));
    }

    @Test
    void indexProduct_setsAutocompleteSuggestions() {
        when(repository.save(any(Product.class))).thenAnswer(inv -> inv.getArgument(0));

        Product result = searchService.indexProduct(sampleProduct);

        assertNotNull(result.getSuggest());
    }

    // ─── deleteProduct ──────────────────────────────────────────────────────

    @Test
    void deleteProduct_callsRepository() {
        doNothing().when(repository).deleteById("prod-001");

        searchService.deleteProduct("prod-001");

        verify(repository).deleteById("prod-001");
    }

    // ─── getById ────────────────────────────────────────────────────────────

    @Test
    void getById_returnsProductWhenFound() {
        when(repository.findById("prod-001")).thenReturn(Optional.of(sampleProduct));

        Optional<Product> result = searchService.getById("prod-001");

        assertTrue(result.isPresent());
        assertEquals("iPhone 15 Pro", result.get().getName());
    }

    @Test
    void getById_returnsEmptyWhenNotFound() {
        when(repository.findById("prod-999")).thenReturn(Optional.empty());

        Optional<Product> result = searchService.getById("prod-999");

        assertTrue(result.isEmpty());
    }
}