package com.ecommerce.search.service;

import com.ecommerce.search.model.Product;
import com.ecommerce.search.repository.ProductSearchRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.elasticsearch.core.ElasticsearchOperations;
import org.springframework.data.elasticsearch.core.SearchHit;
import org.springframework.data.elasticsearch.core.SearchHits;
import org.springframework.data.elasticsearch.core.suggest.Completion;
import org.springframework.data.elasticsearch.core.query.Criteria;
import org.springframework.data.elasticsearch.core.query.CriteriaQuery;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Service
public class SearchService {

    private static final Logger log = LoggerFactory.getLogger(SearchService.class);

    private final ProductSearchRepository repository;
    private final ElasticsearchOperations elasticsearchOperations;

    public SearchService(ProductSearchRepository repository, ElasticsearchOperations elasticsearchOperations) {
        this.repository = repository;
        this.elasticsearchOperations = elasticsearchOperations;
    }

    // ─── Full-Text Search ────────────────────────────────────────────────────

    public List<Product> search(String query) {
        log.info("🔍 Searching for: {}", query);

        Criteria criteria = new Criteria("name").fuzzy(query)
                .or(new Criteria("description").matches(query))
                .or(new Criteria("tags").matches(query))
                .or(new Criteria("category").matches(query));

        CriteriaQuery searchQuery = new CriteriaQuery(criteria);
        SearchHits<Product> hits = elasticsearchOperations.search(searchQuery, Product.class);

        List<Product> results = hits.getSearchHits().stream()
                .map(SearchHit::getContent)
                .toList();

        log.info("🔍 Found {} results for '{}'", results.size(), query);
        return results;
    }

    // ─── Autocomplete ────────────────────────────────────────────────────────

    public List<String> autocomplete(String prefix) {
        log.info("✨ Autocomplete for: {}", prefix);

        // Criteria.contains() builds a wildcard query and rejects values with whitespace,
        // so "iPhone 15" used to fail with a 500. Match each word instead (all must match).
        String[] words = prefix == null ? new String[0] : prefix.trim().split("\\s+");
        if (words.length == 0 || words[0].isEmpty()) {
            return List.of();
        }
        Criteria criteria = new Criteria("name").contains(words[0]);
        for (int i = 1; i < words.length; i++) {
            criteria = criteria.and(new Criteria("name").contains(words[i]));
        }
        CriteriaQuery searchQuery = new CriteriaQuery(criteria);
        SearchHits<Product> hits = elasticsearchOperations.search(searchQuery, Product.class);

        List<String> suggestions = hits.getSearchHits().stream()
                .map(hit -> hit.getContent().getName())
                .distinct()
                .limit(10)
                .toList();

        log.info("✨ {} suggestions for '{}'", suggestions.size(), prefix);
        return suggestions;
    }

    // ─── Faceted Filtering ───────────────────────────────────────────────────

    public List<Product> filter(String category, Double minPrice, Double maxPrice) {
        log.info("🏷️ Filtering: category={}, price={}-{}", category, minPrice, maxPrice);

        Criteria criteria = new Criteria();

        if (category != null && !category.isBlank()) {
            criteria = criteria.and(new Criteria("category").is(category));
        }
        if (minPrice != null && maxPrice != null) {
            criteria = criteria.and(new Criteria("price").between(minPrice, maxPrice));
        } else if (minPrice != null) {
            criteria = criteria.and(new Criteria("price").greaterThanEqual(minPrice));
        } else if (maxPrice != null) {
            criteria = criteria.and(new Criteria("price").lessThanEqual(maxPrice));
        }

        CriteriaQuery searchQuery = new CriteriaQuery(criteria);
        SearchHits<Product> hits = elasticsearchOperations.search(searchQuery, Product.class);

        List<Product> results = hits.getSearchHits().stream()
                .map(SearchHit::getContent)
                .toList();

        log.info("🏷️ Found {} results", results.size());
        return results;
    }

    // ─── Index Management ────────────────────────────────────────────────────

    public Product indexProduct(Product product) {
        String name = product.getName();
        if (name != null) {
            String[] words = name.split("\\s+");
            List<String> inputs = new ArrayList<>();
            inputs.add(name);
            StringBuilder sb = new StringBuilder();
            for (String word : words) {
                if (!sb.isEmpty()) sb.append(" ");
                sb.append(word);
                inputs.add(sb.toString());
            }
            product.setSuggest(new Completion(inputs.toArray(new String[0])));
        }

        Product saved = repository.save(product);
        log.info("📥 Indexed product: {} ({})", saved.getName(), saved.getId());
        return saved;
    }

    public void deleteProduct(String id) {
        repository.deleteById(id);
        log.info("🗑️ Deleted product from index: {}", id);
    }

    public Optional<Product> getById(String id) {
        return repository.findById(id);
    }

    public Iterable<Product> getAll() {
        return repository.findAll();
    }
}