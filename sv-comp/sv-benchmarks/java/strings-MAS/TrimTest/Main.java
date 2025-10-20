import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        test(a1);
    }

    public static void test(String s) {
        if (s.contains(" ")) System.out.println("String contains spaces: "+s);
        String trimmed = s.trim();
        if (trimmed.equals("Hi")) {
            System.out.println("Trimmed string is correct: " + trimmed);
        } else {
            System.out.println("Trimmed string is incorrect: " + trimmed);
        }
    }
}
