import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        String a2 = Verifier.nondetString();
        test(a1, a2);
    }

    public static void test(String s1, String s2) {
        if (s1.substring(5,10).equals(s2)) {
            System.out.println("s1.substring(5) equals s2");
        } else {
            System.out.println("s1.substring(5) does not equal s2");
        }
    }
}
